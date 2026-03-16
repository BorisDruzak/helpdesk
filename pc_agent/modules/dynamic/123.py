from modules.base_module import BaseCollector
import psutil
import time

class NetworkSpeedCollector(BaseCollector):
    def __init__(self):
        # Инициализация состояния (памяти)
        self.last_time = time.time()
        self.last_sent = psutil.net_io_counters().bytes_sent
        self.last_recv = psutil.net_io_counters().bytes_recv

    @property
    def name(self) -> str:
        return "net_speed"

    async def collect(self) -> dict:
        now = time.time()
        current_sent = psutil.net_io_counters().bytes_sent
        current_recv = psutil.net_io_counters().bytes_recv

        # Вычисляем дельту (сколько прошло с прошлого раза)
        time_delta = now - self.last_time
        if time_delta == 0: time_delta = 1 # Защита от деления на 0

        # Скорость в КБ/сек
        speed_sent_kb = (current_sent - self.last_sent) / 1024 / time_delta
        speed_recv_kb = (current_recv - self.last_recv) / 1024 / time_delta

        # Обновляем память для следующего раза
        self.last_sent = current_sent
        self.last_recv = current_recv
        self.last_time = now

        return {
            "upload_speed_kb": round(speed_sent_kb, 2),
            "download_speed_kb": round(speed_recv_kb, 2),
            "interval": round(time_delta, 2)
        }