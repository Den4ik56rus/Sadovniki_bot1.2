# src/api/handlers/server_metrics.py
"""
Сбор системных метрик сервера (CPU, RAM, Disk, Network, Docker).
Читает данные напрямую из /proc и системных утилит.
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone

from aiohttp import web

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)

# Кеш для вычисления CPU usage (нужны два замера)
_prev_cpu: dict | None = None
_prev_cpu_time: float = 0

# Кеш для вычисления network rate
_prev_net: dict | None = None
_prev_net_time: float = 0


def _read_proc_stat() -> dict:
    """Чтение /proc/stat для CPU метрик."""
    try:
        with open('/proc/stat', 'r') as f:
            line = f.readline()  # cpu  user nice system idle iowait irq softirq ...
        parts = line.split()
        return {
            'user': int(parts[1]),
            'nice': int(parts[2]),
            'system': int(parts[3]),
            'idle': int(parts[4]),
            'iowait': int(parts[5]),
            'irq': int(parts[6]),
            'softirq': int(parts[7]),
        }
    except Exception:
        return {}


def _calc_cpu_percent() -> float:
    """Вычисление % загрузки CPU между двумя замерами."""
    global _prev_cpu, _prev_cpu_time

    current = _read_proc_stat()
    now = time.monotonic()

    if not current:
        return 0.0

    if _prev_cpu is None or (now - _prev_cpu_time) > 10:
        # Первый замер или слишком старый — сохраняем и возвращаем 0
        _prev_cpu = current
        _prev_cpu_time = now
        return 0.0

    prev = _prev_cpu
    _prev_cpu = current
    _prev_cpu_time = now

    prev_idle = prev['idle'] + prev['iowait']
    curr_idle = current['idle'] + current['iowait']

    prev_total = sum(prev.values())
    curr_total = sum(current.values())

    total_diff = curr_total - prev_total
    idle_diff = curr_idle - prev_idle

    if total_diff == 0:
        return 0.0

    return round(((total_diff - idle_diff) / total_diff) * 100, 1)


def _read_load_avg() -> dict:
    """Чтение /proc/loadavg."""
    try:
        with open('/proc/loadavg', 'r') as f:
            parts = f.read().split()
        return {
            'load_1m': float(parts[0]),
            'load_5m': float(parts[1]),
            'load_15m': float(parts[2]),
        }
    except Exception:
        return {'load_1m': 0, 'load_5m': 0, 'load_15m': 0}


def _read_cpu_count() -> int:
    """Количество CPU ядер."""
    try:
        count = 0
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('processor'):
                    count += 1
        return count or 1
    except Exception:
        return os.cpu_count() or 1


def _read_meminfo() -> dict:
    """Чтение /proc/meminfo для RAM метрик."""
    try:
        info = {}
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                parts = line.split(':')
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]  # значение в kB
                    info[key] = int(val)

        total = info.get('MemTotal', 0)
        available = info.get('MemAvailable', 0)
        buffers = info.get('Buffers', 0)
        cached = info.get('Cached', 0)
        free = info.get('MemFree', 0)
        swap_total = info.get('SwapTotal', 0)
        swap_free = info.get('SwapFree', 0)

        used = total - available
        used_percent = round((used / total) * 100, 1) if total > 0 else 0

        return {
            'total_mb': round(total / 1024, 0),
            'used_mb': round(used / 1024, 0),
            'available_mb': round(available / 1024, 0),
            'buffers_mb': round(buffers / 1024, 0),
            'cached_mb': round(cached / 1024, 0),
            'free_mb': round(free / 1024, 0),
            'used_percent': used_percent,
            'swap_total_mb': round(swap_total / 1024, 0),
            'swap_used_mb': round((swap_total - swap_free) / 1024, 0),
            'swap_percent': round(((swap_total - swap_free) / swap_total) * 100, 1) if swap_total > 0 else 0,
        }
    except Exception:
        return {
            'total_mb': 0, 'used_mb': 0, 'available_mb': 0,
            'buffers_mb': 0, 'cached_mb': 0, 'free_mb': 0,
            'used_percent': 0, 'swap_total_mb': 0, 'swap_used_mb': 0, 'swap_percent': 0,
        }


def _read_disk() -> dict:
    """Чтение использования диска через statvfs."""
    try:
        stat = os.statvfs('/')
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bfree * stat.f_frsize
        available = stat.f_bavail * stat.f_frsize
        used = total - free

        return {
            'total_gb': round(total / (1024 ** 3), 1),
            'used_gb': round(used / (1024 ** 3), 1),
            'available_gb': round(available / (1024 ** 3), 1),
            'used_percent': round((used / total) * 100, 1) if total > 0 else 0,
        }
    except Exception:
        return {'total_gb': 0, 'used_gb': 0, 'available_gb': 0, 'used_percent': 0}


def _read_disk_io() -> dict:
    """Чтение /proc/diskstats для I/O метрик."""
    try:
        with open('/proc/diskstats', 'r') as f:
            lines = f.readlines()

        total_reads = 0
        total_writes = 0
        for line in lines:
            parts = line.split()
            if len(parts) >= 14:
                name = parts[2]
                # Только основные диски (sda, vda, nvme0n1), не партиции
                if name.startswith(('sd', 'vd', 'nvme')) and not any(c.isdigit() for c in name[-1:] if name.startswith(('sd', 'vd'))):
                    total_reads += int(parts[5])   # sectors read
                    total_writes += int(parts[9])  # sectors written

        # Конвертация секторов (512 bytes) в MB
        return {
            'read_mb': round(total_reads * 512 / (1024 ** 2), 1),
            'write_mb': round(total_writes * 512 / (1024 ** 2), 1),
        }
    except Exception:
        return {'read_mb': 0, 'write_mb': 0}


def _read_network() -> dict:
    """Чтение /proc/net/dev для сетевых метрик."""
    global _prev_net, _prev_net_time

    try:
        now = time.monotonic()
        with open('/proc/net/dev', 'r') as f:
            lines = f.readlines()

        total_rx = 0
        total_tx = 0
        for line in lines[2:]:  # Первые две строки — заголовки
            parts = line.split()
            iface = parts[0].rstrip(':')
            if iface == 'lo':
                continue  # Пропускаем loopback
            total_rx += int(parts[1])   # bytes received
            total_tx += int(parts[9])   # bytes transmitted

        current = {'rx': total_rx, 'tx': total_tx}

        rx_rate = 0.0
        tx_rate = 0.0

        if _prev_net is not None:
            dt = now - _prev_net_time
            if dt > 0:
                rx_rate = round((total_rx - _prev_net['rx']) / dt / 1024, 1)  # KB/s
                tx_rate = round((total_tx - _prev_net['tx']) / dt / 1024, 1)  # KB/s

        _prev_net = current
        _prev_net_time = now

        return {
            'rx_total_mb': round(total_rx / (1024 ** 2), 1),
            'tx_total_mb': round(total_tx / (1024 ** 2), 1),
            'rx_rate_kbps': max(0, rx_rate),
            'tx_rate_kbps': max(0, tx_rate),
        }
    except Exception:
        return {
            'rx_total_mb': 0, 'tx_total_mb': 0,
            'rx_rate_kbps': 0, 'tx_rate_kbps': 0,
        }


def _read_uptime() -> dict:
    """Чтение /proc/uptime."""
    try:
        with open('/proc/uptime', 'r') as f:
            parts = f.read().split()
        uptime_seconds = float(parts[0])
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        return {
            'seconds': round(uptime_seconds),
            'formatted': f'{days}d {hours}h {minutes}m',
        }
    except Exception:
        return {'seconds': 0, 'formatted': 'N/A'}


async def _get_docker_stats() -> list:
    """Получение статистики Docker контейнеров."""
    try:
        proc = await asyncio.create_subprocess_exec(
            'docker', 'stats', '--no-stream', '--format',
            '{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.PIDs}}',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)

        containers = []
        for line in stdout.decode().strip().split('\n'):
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) >= 6:
                containers.append({
                    'name': parts[0],
                    'cpu': parts[1],
                    'mem_usage': parts[2],
                    'mem_percent': parts[3],
                    'net_io': parts[4],
                    'pids': parts[5],
                })
        return containers
    except Exception:
        return []


async def get_server_metrics(request: web.Request) -> web.Response:
    """GET /api/admin/server-metrics — текущие метрики сервера."""
    try:
        # Собираем все метрики
        cpu_percent = _calc_cpu_percent()
        load_avg = _read_load_avg()
        cpu_count = _read_cpu_count()
        memory = _read_meminfo()
        disk = _read_disk()
        disk_io = _read_disk_io()
        network = _read_network()
        uptime = _read_uptime()
        docker = await _get_docker_stats()

        return web.json_response({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'cpu': {
                'percent': cpu_percent,
                'cores': cpu_count,
                **load_avg,
            },
            'memory': memory,
            'disk': disk,
            'disk_io': disk_io,
            'network': network,
            'uptime': uptime,
            'docker': docker,
        })
    except Exception as e:
        logger.error(f"Error collecting server metrics: {e}")
        raise web.HTTPInternalServerError(text="Failed to collect metrics")


async def get_server_metrics_history(request: web.Request) -> web.Response:
    """GET /api/admin/server-metrics/history — история метрик для графиков."""
    try:
        hours = int(request.query.get('hours', 24))
        hours = min(hours, 168)  # Максимум 7 дней

        pool = get_pool()
        rows = await pool.fetch("""
            SELECT
                recorded_at,
                cpu_percent,
                memory_used_percent,
                disk_used_percent,
                network_rx_kbps,
                network_tx_kbps,
                load_1m
            FROM server_metrics_history
            WHERE recorded_at > NOW() - ($1 || ' hours')::interval
            ORDER BY recorded_at ASC
        """, str(hours))

        history = []
        for row in rows:
            history.append({
                'time': row['recorded_at'].isoformat(),
                'cpu': float(row['cpu_percent']),
                'memory': float(row['memory_used_percent']),
                'disk': float(row['disk_used_percent']),
                'net_rx': float(row['network_rx_kbps']),
                'net_tx': float(row['network_tx_kbps']),
                'load': float(row['load_1m']),
            })

        return web.json_response({'history': history, 'hours': hours})
    except Exception as e:
        logger.error(f"Error fetching metrics history: {e}")
        raise web.HTTPInternalServerError(text="Failed to fetch history")


async def record_metrics_snapshot():
    """
    Записать текущий снапшот метрик в БД.
    Вызывается периодически (каждые 5 минут) из фонового таска.
    """
    try:
        pool = get_pool()
        if pool is None:
            return

        cpu_percent = _calc_cpu_percent()
        load_avg = _read_load_avg()
        memory = _read_meminfo()
        disk = _read_disk()
        network = _read_network()

        await pool.execute("""
            INSERT INTO server_metrics_history
                (cpu_percent, memory_used_percent, disk_used_percent,
                 network_rx_kbps, network_tx_kbps, load_1m,
                 memory_used_mb, memory_total_mb, disk_used_gb, disk_total_gb)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
            cpu_percent,
            memory['used_percent'],
            disk['used_percent'],
            network['rx_rate_kbps'],
            network['tx_rate_kbps'],
            load_avg['load_1m'],
            memory['used_mb'],
            memory['total_mb'],
            disk['used_gb'],
            disk['total_gb'],
        )

        # Удаляем записи старше 7 дней
        await pool.execute("""
            DELETE FROM server_metrics_history
            WHERE recorded_at < NOW() - INTERVAL '7 days'
        """)
    except Exception as e:
        logger.error(f"Error recording metrics snapshot: {e}")


async def start_metrics_collector(app: web.Application):
    """Фоновый таск для периодической записи метрик."""
    async def collector():
        # Первый замер CPU (нужен для вычисления diff)
        _calc_cpu_percent()
        _read_network()
        await asyncio.sleep(2)

        while True:
            try:
                await record_metrics_snapshot()
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
            await asyncio.sleep(300)  # Каждые 5 минут

    app['metrics_collector'] = asyncio.create_task(collector())


async def stop_metrics_collector(app: web.Application):
    """Остановка фонового таска."""
    task = app.get('metrics_collector')
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
