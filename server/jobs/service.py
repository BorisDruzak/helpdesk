"""
Бизнес-логика для работы с jobs.
"""

from typing import List, Dict
from loguru import logger


class JobsService:
    """Сервис для работы с jobs."""
    
    def __init__(self, state_manager):
        self.state = state_manager
    
    def get_events(self, job_id: str) -> List[dict]:
        """
        Возвращает события job.
        
        Args:
            job_id: ID job
        
        Returns:
            list: Список событий
        """
        return self.state.get_job_events(job_id)
    
    def append_event(self, job_id: str, event: dict) -> None:
        """
        Добавляет событие в журнал job.
        
        Args:
            job_id: ID job
            event: Событие для добавления
        """
        self.state.append_job_event(job_id, event)
        logger.debug(f"[JobsService] Event added to job: job_id={job_id}")
    
    def clear_events(self, job_id: str) -> None:
        """
        Очищает события job.
        
        Args:
            job_id: ID job
        """
        self.state.clear_job_events(job_id)
        logger.info(f"[JobsService] Cleared events for job: job_id={job_id}")




