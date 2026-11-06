"""Canonical public message for an explicitly requester-authored reopen."""
import uuid
from tickets.statuses import enrich_chat_payload_with_requester_name

REOPEN_REASON_LABELS = {
    'problem_returned': 'Проблема повторилась', 'not_resolved': 'Проблема не решена',
    'incomplete_work': 'Работа выполнена не полностью', 'wrong_resolution': 'Решение не подходит',
    'unclear_instruction': 'Непонятная инструкция', 'requester_disagreed': 'Не согласен с решением',
    'closed_too_early': 'Закрыто слишком рано', 'new_information': 'Появилась новая информация',
    'wrong_category_or_queue': 'Нужна другая команда', 'dependency_failed': 'Смежная проблема не устранена',
    'knowledge_article_failed': 'Статья не помогла', 'other': 'Другая причина',
}


def reopen_message_payload(ticket, *, reopen_id, reason_code, reason_comment):
    reason = REOPEN_REASON_LABELS[reason_code]
    text = f'Обращение возвращено в работу.\nПричина: {reason}'
    comment = str(reason_comment or '').strip()
    if comment:
        text += '\nКомментарий: ' + comment
    message_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'helpdesk:requester-reopen:{ticket.ticket_id}:{reopen_id}'))
    return enrich_chat_payload_with_requester_name(ticket, {
        'message_id': message_id, 'sender_role': 'user', 'from': 'user', 'text': text,
        'visibility': 'public', 'metadata': {'source': 'requester_reopen', 'reopen_id': str(reopen_id), 'reason_code': reason_code},
    })
