"""
HTTP обработчики для jobs API.
"""

import asyncio
from aiohttp import web
from loguru import logger
from websocket.protocol import send_ws_command


async def handle_get_job_events(request):
    """
    API эндпоинт для получения событий job: GET /api/job_events?job_id=...
    
    Возвращает список событий для указанного job_id.
    """
    try:
        state = request.app['state']
        
        job_id = request.query.get("job_id")
        
        if not job_id:
            return web.json_response({
                "status": "error",
                "error": "Missing job_id parameter"
            }, status=400)
        
        # Получаем события для job_id
        events = state.get_job_events(job_id)
        
        return web.json_response({
            "job_id": job_id,
            "events": events,
            "count": len(events)
        })
    
    except Exception as e:
        logger.error(f"❌ Ошибка получения job_events: {e}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_start_job(request):
    """
    API эндпоинт для запуска job: POST /api/start_job
    
    POST JSON:
    {
      "device_id": "test_pc_01",
      "job_type": "chat_echo",
      "params": {},
      "actor_role": "admin"
    }
    
    Вызывает send_ws_command с командой "start_job".
    """
    try:
        state = request.app['state']
        
        data = await request.json()
        device_id = data.get("device_id")
        job_type = data.get("job_type")
        params = data.get("params", {})
        actor_role = data.get("actor_role", "admin")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if not job_type:
            return web.json_response({
                "status": "error",
                "error": "Missing job_type"
            }, status=400)
        
        logger.info(f"[SERVER] start_job device_id={device_id} job_type={job_type} actor_role={actor_role}")
        
        # Формируем параметры команды start_job
        command_params = {
            "job_type": job_type,
            "params": params
        }
        
        # Отправляем команду агенту
        response = await send_ws_command(
            state=state,
            device_id=device_id,
            command="start_job",
            params=command_params,
            actor_role=actor_role,
            timeout=60
        )
        
        # Извлекаем payload из ответа
        if isinstance(response, dict) and "payload" in response:
            response_payload = response["payload"]
        else:
            response_payload = response
        
        return web.json_response({
            "status": "success" if response_payload.get("status") == "success" else "error",
            "device_id": device_id,
            "job_type": job_type,
            "response": response_payload
        })
    
    except ValueError as e:
        logger.warning(f"⚠️  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды start_job")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки start_job: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)




