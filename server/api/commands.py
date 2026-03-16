"""
API обработчики для команд агента.
"""

import asyncio
from aiohttp import web
from loguru import logger
from websocket.protocol import send_ws_command


async def handle_send_command(request):
    """
    API эндпоинт для отправки команд агенту (relay-архитектура).
    
    Сервер пересылает команду агенту через WebSocket и ожидает ответ.
    Агент обрабатывает команду через свой AgentOrchestrator и возвращает результат.
    
    Поддерживаемые команды (обрабатываются на стороне агента):
    - ping: проверка статуса агента
    - collect: сбор данных с модулей
    - list_modules: список загруженных модулей
    - exec_script: выполнение скрипта в памяти
    - get_status: расширенный статус агента
    - get_info: системная информация
    - get_history: история событий из БД
    """
    try:
        state = request.app['state']
        
        logger.debug("🔍 Получен запрос /api/send_command")
        data = await request.json()
        logger.debug(f"📥 Данные запроса: {data}")
        
        device_id = data.get("device_id")
        command = data.get("command")
        params = data.get("params", {})
        actor_role = data.get("actor_role", "user")
        
        logger.debug(f"🔧 device_id={device_id}, command={command}, params={params}, actor_role={actor_role}")
        
        if not device_id or not command:
            logger.warning("⚠️  Отсутствует device_id или command")
            return web.json_response({
                "status": "error",
                "error": "Missing device_id or command"
            }, status=400)
        
        # Используем универсальную функцию send_ws_command
        response = await send_ws_command(
            state=state,
            device_id=device_id,
            command=command,
            params=params,
            actor_role=actor_role,
            timeout=30
        )
        
        # Возвращаем payload из command_result (или весь response, если payload нет)
        if isinstance(response, dict) and "payload" in response:
            return web.json_response(response["payload"])
        else:
            return web.json_response(response)
    
    except ValueError as e:
        logger.warning(f"⚠️  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки команды: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_check_functions(request):
    """
    API эндпоинт для проверки доступных функций агента: POST /api/check_functions
    
    Проверяет существующие функции ПК агента через команды:
    - get_manifest - получение манифеста всех модулей и их методов
    - list_tools - список всех доступных инструментов
    - list_modules - список загруженных модулей
    
    Returns:
        JSON с информацией о доступных функциях агента
    """
    try:
        state = request.app['state']
        
        logger.debug("🔍 Получен запрос /api/check_functions")
        data = await request.json()
        logger.debug(f"📥 Данные запроса: {data}")
        
        device_id = data.get("device_id")
        
        if not device_id:
            logger.warning("⚠️  Отсутствует device_id")
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if not state.is_agent_online(device_id):
            logger.warning(f"⚠️  Агент {device_id} не подключен")
            return web.json_response({
                "status": "error",
                "error": f"Agent {device_id} not connected"
            }, status=404)
        
        # Собираем информацию о функциях через несколько команд
        functions_info = {
            "device_id": device_id,
            "core_commands": [],
            "modules": [],
            "tools": [],
            "manifest": None
        }
        
        # 1. Получаем манифест (полная информация о модулях и методах)
        try:
            logger.info(f"📋 Запрос манифеста от агента {device_id}")
            
            response = await send_ws_command(
                state=state,
                device_id=device_id,
                command="get_manifest",
                params={},
                actor_role="admin",
                timeout=30
            )
            
            # Извлекаем payload из command_result
            if isinstance(response, dict) and "payload" in response:
                response_payload = response["payload"]
            else:
                response_payload = response
            
            if response_payload.get("status") == "success" and "data" in response_payload:
                manifest = response_payload["data"].get("observations", {}).get("manifest", {})
                functions_info["manifest"] = manifest
                
                # Извлекаем список модулей из манифеста
                for module_name, module_info in manifest.items():
                    if module_name == "core":
                        # Core команды
                        methods = module_info.get("methods", {})
                        for method_name, method_info in methods.items():
                            functions_info["core_commands"].append({
                                "name": method_name,
                                "description": method_info.get("description", ""),
                                "module": "core"
                            })
                    else:
                        # Модули
                        methods = module_info.get("methods", {})
                        module_tools = []
                        for method_name, method_info in methods.items():
                            tool_name = method_info.get("tool_name", method_name)
                            module_tools.append({
                                "name": tool_name,
                                "description": method_info.get("description", ""),
                                "risk_level": method_info.get("risk_level", "safe_readonly"),
                                "async": method_info.get("async", False)
                            })
                        
                        functions_info["modules"].append({
                            "name": module_name,
                            "description": module_info.get("description", ""),
                            "tools": module_tools
                        })
                
                logger.success(f"✅ Манифест получен: {len(manifest)} разделов")
        
        except asyncio.TimeoutError:
            logger.warning(f"⏱️  Таймаут получения манифеста от агента {device_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка получения манифеста: {e}")
        
        # 2. Получаем список инструментов (плоский список)
        try:
            logger.info(f"📋 Запрос списка инструментов от агента {device_id}")
            
            response = await send_ws_command(
                state=state,
                device_id=device_id,
                command="list_tools",
                params={},
                actor_role="admin",
                timeout=30
            )
            
            # Извлекаем payload из command_result
            if isinstance(response, dict) and "payload" in response:
                response_payload = response["payload"]
            else:
                response_payload = response
            
            if response_payload.get("status") == "success" and "data" in response_payload:
                tools = response_payload["data"].get("observations", {}).get("tools", [])
                functions_info["tools"] = tools
                logger.success(f"✅ Список инструментов получен: {len(tools)} инструментов")
        
        except asyncio.TimeoutError:
            logger.warning(f"⏱️  Таймаут получения списка инструментов от агента {device_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка инструментов: {e}")
        
        # 3. Получаем список модулей (для проверки)
        try:
            logger.info(f"📋 Запрос списка модулей от агента {device_id}")
            
            response = await send_ws_command(
                state=state,
                device_id=device_id,
                command="list_modules",
                params={},
                actor_role="admin",
                timeout=30
            )
            
            # Извлекаем payload из command_result
            if isinstance(response, dict) and "payload" in response:
                response_payload = response["payload"]
            else:
                response_payload = response
            
            if response_payload.get("status") == "success" and "data" in response_payload:
                modules_list = response_payload["data"].get("observations", {}).get("modules", [])
                # Обновляем информацию о модулях, если она есть
                if modules_list:
                    logger.success(f"✅ Список модулей получен: {len(modules_list)} модулей")
        
        except asyncio.TimeoutError:
            logger.warning(f"⏱️  Таймаут получения списка модулей от агента {device_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка модулей: {e}")
        
        # Формируем итоговый ответ
        return web.json_response({
            "status": "success",
            "data": functions_info
        })
    
    except Exception as e:
        logger.error(f"❌ Ошибка проверки функций: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_smoke_run(request):
    """
    API эндпоинт для smoke-теста: проверка работоспособности через list_tools и run_tool.
    
    POST JSON:
    {
      "device_id": "test_pc_01",
      "tool": "diag.hello",
      "params": {},
      "actor_role": "admin"
    }
    """
    try:
        state = request.app['state']
        
        logger.info("[SERVER] /api/smoke_run RX")
        data = await request.json()
        
        device_id = data.get("device_id")
        tool = data.get("tool")
        params = data.get("params", {})
        actor_role = data.get("actor_role", "admin")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if not tool:
            return web.json_response({
                "status": "error",
                "error": "Missing tool"
            }, status=400)
        
        logger.info(f"[SERVER] /api/smoke_run device_id={device_id} tool={tool}")
        
        # Шаг 1: list_tools
        tools_res = await send_ws_command(
            state=state,
            device_id=device_id,
            command="list_tools",
            params={},
            actor_role=actor_role
        )
        tools_payload = tools_res.get("payload", tools_res) if isinstance(tools_res, dict) else tools_res
        
        # Проверяем, что tool в списке
        tool_exists = False
        tools_list = []
        if tools_payload.get("status") == "success":
            observations = tools_payload.get("data", {}).get("observations", {})
            tools_list = observations.get("tools", [])
            tool_exists = any(t.get("name") == tool for t in tools_list)
        
        if not tool_exists:
            return web.json_response({
                "status": "error",
                "error": f"Tool '{tool}' not found in tools list",
                "device_id": device_id,
                "tool_exists": False,
                "list_tools": tools_payload
            }, status=409)
        
        # Шаг 2: run_tool
        agent_params = {
            "tool": tool,
            "params": params
        }
        run_res = await send_ws_command(
            state=state,
            device_id=device_id,
            command="run_tool",
            params=agent_params,
            actor_role=actor_role
        )
        
        return web.json_response({
            "status": "success",
            "device_id": device_id,
            "tool_exists": True,
            "list_tools": tools_payload,
            "run_tool": run_res
        })
    
    except ValueError as e:
        logger.warning(f"⚠️  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды smoke_run")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки smoke_run: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)




