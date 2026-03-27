        let pollInterval = null;
        let currentTools = [];
        let selectedTool = null;
        let currentEditorTab = 'form';
        let appInitialized = false;
        let authSessionInvalid = false;
        
        // Auth header for API calls (admin uses admin_auth_token from localStorage)
        function getAuthHeaders(includeContentType) {
            const token = localStorage.getItem('admin_auth_token');
            const headers = {};
            if (token) headers['Authorization'] = 'Bearer ' + token;
            if (includeContentType) headers['Content-Type'] = 'application/json';
            return headers;
        }

        /** Безопасный разбор ответа как JSON (избегает ошибки при HTML/не-JSON). */
        async function responseToJson(response) {
            const text = await response.text();
            if (!text || !text.trim()) return {};
            try {
                return JSON.parse(text);
            } catch (e) {
                const preview = text.slice(0, 120).replace(/\s+/g, ' ');
                throw new Error('Сервер вернул не JSON (возможно, требуется вход в панель). ' + (preview ? ' Ответ: ' + preview : ''));
            }
        }
        
        // Initialize (will be called after successful login)
        function initializeApp() {
            if (authSessionInvalid) {
                return;
            }
            if (appInitialized) {
                return; // Prevent double initialization
            }
            appInitialized = true;
            loadAgents();
            loadTickets();
            loadPendingConnections();
            startPolling();
        }
        
        // Don't auto-initialize - wait for authentication
        // document.addEventListener('DOMContentLoaded', () => {
        //     initializeApp();
        // });
        
        // Polling
        function startPolling() {
            if (authSessionInvalid) {
                return;
            }
            // Poll every 3 seconds
            pollInterval = setInterval(() => {
                loadAgents();
                loadTickets();
                loadPendingConnections();
            }, 3000);
        }
        
        function stopPolling() {
            if (pollInterval) {
                clearInterval(pollInterval);
                pollInterval = null;
            }
        }
        
        // Load Agents
        async function loadAgents() {
            if (authSessionInvalid) {
                return;
            }
            try {
                const response = await fetch('/api/agents', { headers: getAuthHeaders() });
                const data = await response.json();
                
                if (response.ok && data.status === 'ok') {
                    updateAgentStatus(data.agents || []);
                    updateDeviceSelector(data.agents || []);
                } else {
                    if (response.status === 401) console.warn('Auth required for /api/agents');
                    updateAgentStatus([]);
                }
            } catch (error) {
                console.error('Error loading agents:', error);
                updateAgentStatus([]);
            }
        }
        
        function updateAgentStatus(agents) {
            const container = document.getElementById('agentStatusContainer');
            
            if (agents.length === 0) {
                container.innerHTML = `
                    <div class="agent-status agent-offline">
                        <span class="status-indicator"></span>
                        Не в сети (0 агентов)
                    </div>
                `;
            } else {
                container.innerHTML = `
                    <div class="agent-status agent-online">
                        <span class="status-indicator"></span>
                        В сети (${agents.length} ${agents.length > 1 ? 'агента' : 'агент'})
                    </div>
                `;
            }
        }
        
        function updateDeviceSelector(agents) {
            const select = document.getElementById('deviceSelect');
            const currentValue = select.value;
            
            select.innerHTML = '<option value="">-- Выберите устройство --</option>';
            
            agents.forEach(agent => {
                const option = document.createElement('option');
                option.value = agent.device_id;
                option.textContent = `${agent.device_id} (${agent.user_display_name || 'Неизвестно'})`;
                select.appendChild(option);
            });
            
            // Restore selection if still available
            if (currentValue && agents.some(a => a.device_id === currentValue)) {
                select.value = currentValue;
            }
        }
        
        // Load Tickets
        async function loadTickets() {
            if (authSessionInvalid) {
                return;
            }
            try {
                const response = await fetch('/api/tickets', { headers: getAuthHeaders() });
                const data = await response.json();
                
                const loadingEl = document.getElementById('ticketsLoading');
                const errorEl = document.getElementById('ticketsError');
                const containerEl = document.getElementById('ticketsContainer');
                const emptyEl = document.getElementById('ticketsEmpty');
                
                loadingEl.style.display = 'none';
                errorEl.style.display = 'none';
                
                if (data.status === 'ok') {
                    const tickets = data.tickets || [];
                    
                    if (tickets.length === 0) {
                        containerEl.style.display = 'none';
                        emptyEl.style.display = 'block';
                    } else {
                        emptyEl.style.display = 'none';
                        containerEl.style.display = 'block';
                        renderTicketsTable(tickets);
                    }
                } else {
                    errorEl.textContent = `Ошибка: ${data.error || 'Неизвестная ошибка'}`;
                    errorEl.style.display = 'block';
                    containerEl.style.display = 'none';
                    emptyEl.style.display = 'none';
                }
            } catch (error) {
                console.error('Error loading tickets:', error);
                const errorEl = document.getElementById('ticketsError');
                errorEl.textContent = `Ошибка: ${error.message}`;
                errorEl.style.display = 'block';
                document.getElementById('ticketsLoading').style.display = 'none';
                document.getElementById('ticketsContainer').style.display = 'none';
            }
        }
        
        function renderTicketsTable(tickets) {
            const tbody = document.getElementById('ticketsTableBody');
            tbody.innerHTML = '';
            
            // Sort by updated_at descending
            tickets.sort((a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0));
            
            tickets.forEach(ticketData => {
                // Поддержка старого формата (когда tickets это массив объектов ticket) и нового (с ticket и session)
                const ticket = ticketData.ticket || ticketData;
                
                const row = document.createElement('tr');
                
                const statusClass = ticket.status === 'open' ? 'status-open' : 
                                   ticket.status === 'closed' ? 'status-closed' : 'status-pending';
                
                const tags = (ticket.tags || []).map(tag => 
                    `<span class="tag">${tag}</span>`
                ).join('');
                
                const updatedAt = ticket.updated_at ?
                    new Date(ticket.updated_at).toLocaleString('ru-RU') : '—';
                
                // Индикатор online/offline агента
                const agentOnline = ticket.agent_online || false;
                const agentStatusClass = agentOnline ? 'agent-online' : 'agent-offline';
                const agentStatusText = agentOnline ? '🟢 В сети' : '🔴 Не в сети';
                
                row.innerHTML = `
                    <td><a href="#" onclick="queueOpenWorkbench('${ticket.ticket_id}'); return false;" class="ticket-link">${ticket.ticket_id}</a></td>
                    <td>${ticket.device_id || '—'}</td>
                    <td><span class="agent-status ${agentStatusClass}" style="font-size: 11px; padding: 3px 8px;">${agentStatusText}</span></td>
                    <td>${ticket.user_display_name || '—'}</td>
                    <td>${ticket.title || 'Без названия'}</td>
                    <td><span class="status-badge ${statusClass}">${ticket.status || 'неизвестно'}</span></td>
                    <td>${updatedAt}</td>
                    <td>${ticket.assigned_to || '-'}</td>
                    <td>${tags || '-'}</td>
                `;
                
                tbody.appendChild(row);
            });
        }
        
        // Load Tools
        async function loadTools() {
            const deviceId = document.getElementById('deviceSelect').value;
            
            if (!deviceId) {
                alert('Сначала выберите устройство');
                return;
            }
            
            const loadingEl = document.getElementById('toolsLoading');
            const errorEl = document.getElementById('toolsError');
            const containerEl = document.getElementById('toolsContainer');
            const emptyEl = document.getElementById('toolsEmpty');
            
            loadingEl.style.display = 'block';
            errorEl.style.display = 'none';
            containerEl.style.display = 'none';
            emptyEl.style.display = 'none';
            
            try {
                const response = await fetch(`/api/tools?device_id=${deviceId}`, { headers: getAuthHeaders() });
                const data = await response.json();
                
                loadingEl.style.display = 'none';
                
                if (data.status === 'ok') {
                    currentTools = data.tools || [];
                    
                    if (currentTools.length === 0) {
                        emptyEl.style.display = 'block';
                    } else {
                        containerEl.style.display = 'block';
                        renderToolsList(currentTools);
                    }
                } else {
                    errorEl.textContent = `Ошибка: ${data.error || 'Неизвестная ошибка'}`;
                    errorEl.style.display = 'block';
                }
            } catch (error) {
                console.error('Error loading tools:', error);
                loadingEl.style.display = 'none';
                errorEl.textContent = `Ошибка: ${error.message}`;
                errorEl.style.display = 'block';
            }
        }
        
        function renderToolsList(tools) {
            const listEl = document.getElementById('toolsList');
            listEl.innerHTML = '';
            
            tools.forEach((tool, index) => {
                const toolEl = document.createElement('div');
                toolEl.className = 'tool-item';
                toolEl.onclick = () => selectTool(index);
                
                const riskClass = tool.risk_level === 'low' ? 'badge-low' : 
                                 tool.risk_level === 'medium' ? 'badge-medium' : 'badge-high';
                
                const allowRoles = (tool.allow_roles || []).join(', ') || 'не указаны';
                const requiresConsent = tool.requires_consent ? 'требуется согласие' : 'без согласия';
                
                toolEl.innerHTML = `
                    <div class="tool-header">
                        <span class="tool-name">${tool.name || 'Без названия'}</span>
                        <div class="tool-badges">
                            <span class="badge ${riskClass}">${tool.risk_level || 'неизвестно'}</span>
                            <span class="badge">${requiresConsent}</span>
                        </div>
                    </div>
                    <div class="tool-description">${tool.description || 'Без описания'}</div>
                    <div class="tool-module">Модуль: ${tool.module || 'неизвестно'} | Роли: ${allowRoles}</div>
                `;
                
                listEl.appendChild(toolEl);
            });
        }
        
        function selectTool(index) {
            selectedTool = currentTools[index];
            
            // Update selected state
            const toolItems = document.querySelectorAll('.tool-item');
            toolItems.forEach((item, i) => {
                item.classList.toggle('selected', i === index);
            });
            
            // Show editor
            document.getElementById('toolEditor').style.display = 'block';
            document.getElementById('toolEditorTitle').textContent = `Tool: ${selectedTool.name}`;
            
            // Build form
            buildParamsForm(selectedTool.params_schema || {});
            
            // Reset result
            document.getElementById('toolResult').style.display = 'none';
        }
        
        function clearToolSelection() {
            selectedTool = null;
            document.getElementById('toolEditor').style.display = 'none';
            
            const toolItems = document.querySelectorAll('.tool-item');
            toolItems.forEach(item => item.classList.remove('selected'));
        }
        
        function buildParamsForm(schema) {
            const formEl = document.getElementById('paramsForm');
            formEl.innerHTML = '';
            
            if (!schema.properties || Object.keys(schema.properties).length === 0) {
                formEl.innerHTML = '<p style="color: #8e8e93;">This tool has no parameters</p>';
                document.getElementById('paramsJsonInput').value = '{}';
                return;
            }
            
            const params = {};
            
            for (const [key, prop] of Object.entries(schema.properties)) {
                const groupEl = document.createElement('div');
                groupEl.className = 'form-group';
                
                const label = document.createElement('label');
                label.textContent = `${key}${schema.required?.includes(key) ? ' *' : ''}`;
                groupEl.appendChild(label);
                
                let inputEl;
                
                if (prop.type === 'boolean') {
                    inputEl = document.createElement('select');
                    inputEl.innerHTML = `
                        <option value="true">true</option>
                        <option value="false">false</option>
                    `;
                    params[key] = true;
                } else if (prop.type === 'number' || prop.type === 'integer') {
                    inputEl = document.createElement('input');
                    inputEl.type = 'number';
                    inputEl.placeholder = prop.description || key;
                    params[key] = 0;
                } else if (prop.enum) {
                    inputEl = document.createElement('select');
                    prop.enum.forEach(val => {
                        const option = document.createElement('option');
                        option.value = val;
                        option.textContent = val;
                        inputEl.appendChild(option);
                    });
                    params[key] = prop.enum[0];
                } else {
                    inputEl = document.createElement('input');
                    inputEl.type = 'text';
                    inputEl.placeholder = prop.description || key;
                    params[key] = '';
                }
                
                inputEl.id = `param_${key}`;
                inputEl.dataset.paramKey = key;
                inputEl.dataset.paramType = prop.type;
                
                inputEl.addEventListener('input', updateJsonFromForm);
                
                groupEl.appendChild(inputEl);
                
                if (prop.description) {
                    const desc = document.createElement('small');
                    desc.style.color = '#8e8e93';
                    desc.textContent = prop.description;
                    groupEl.appendChild(desc);
                }
                
                formEl.appendChild(groupEl);
            }
            
            // Initialize JSON
            document.getElementById('paramsJsonInput').value = JSON.stringify(params, null, 2);
        }
        
        function updateJsonFromForm() {
            const params = {};
            const inputs = document.querySelectorAll('[data-param-key]');
            
            inputs.forEach(input => {
                const key = input.dataset.paramKey;
                const type = input.dataset.paramType;
                let value = input.value;
                
                if (type === 'boolean') {
                    value = value === 'true';
                } else if (type === 'number' || type === 'integer') {
                    value = parseFloat(value) || 0;
                }
                
                params[key] = value;
            });
            
            document.getElementById('paramsJsonInput').value = JSON.stringify(params, null, 2);
        }
        
        function switchEditorTab(tab) {
            currentEditorTab = tab;
            
            // Update tabs
            document.querySelectorAll('.editor-tab').forEach(btn => {
                btn.classList.toggle('active', btn.textContent.toLowerCase().includes(tab));
            });
            
            // Update content
            document.querySelectorAll('.editor-content').forEach(content => {
                content.classList.toggle('active', content.id.includes(tab === 'form' ? 'form' : 'json'));
            });
            
            // Sync JSON to form if switching to form
            if (tab === 'form') {
                try {
                    const params = JSON.parse(document.getElementById('paramsJsonInput').value);
                    
                    for (const [key, value] of Object.entries(params)) {
                        const input = document.getElementById(`param_${key}`);
                        if (input) {
                            input.value = value;
                        }
                    }
                } catch (e) {
                    console.error('Invalid JSON:', e);
                }
            }
        }
        
        async function runTool() {
            if (!selectedTool) {
                alert('Инструмент не выбран');
                return;
            }
            
            const deviceId = document.getElementById('deviceSelect').value;
            if (!deviceId) {
                alert('Выберите устройство');
                return;
            }
            
            let params;
            try {
                params = JSON.parse(document.getElementById('paramsJsonInput').value);
            } catch (e) {
                alert('Некорректный JSON параметров: ' + e.message);
                return;
            }
            
            const resultEl = document.getElementById('toolResult');
            const contentEl = document.getElementById('toolResultContent');
            
            resultEl.style.display = 'block';
            contentEl.innerHTML = '<p style="color: #8e8e93;">Выполнение инструмента...</p>';
            
            try {
                const response = await fetch('/api/admin/run_tool', {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({
                        device_id: deviceId,
                        tool_name: selectedTool.name,
                        params: params,
                        mode: 'system_ticket'
                    })
                });
                
                const data = await response.json();
                
                if (data.status === 'ok') {
                    contentEl.innerHTML = `
                        <div class="success-message">
                            Инструмент выполнен успешно!<br>
                            <a href="/ticket.html?ticket_id=${data.ticket_id}" class="ticket-link" target="_blank">
                                Открыть тикет ${data.ticket_id}
                            </a>
                        </div>
                        <pre>${JSON.stringify(data.result, null, 2)}</pre>
                    `;
                    
                    // Refresh tickets
                    loadTickets();
                } else {
                    contentEl.innerHTML = `
                        <div class="error-message">
                            Ошибка: ${data.error || 'Неизвестная ошибка'}<br>
                            ${data.details ? JSON.stringify(data.details) : ''}
                        </div>
                        <pre>${JSON.stringify(data, null, 2)}</pre>
                    `;
                }
            } catch (error) {
                console.error('Error running tool:', error);
                contentEl.innerHTML = `
                    <div class="error-message">
                        Ошибка: ${error.message}
                    </div>
                `;
            }
        }
        
        function refreshAll() {
            loadAgents();
            loadTickets();
            
            const deviceId = document.getElementById('deviceSelect').value;
            if (deviceId && currentTools.length > 0) {
                loadTools();
            }
        }

        // Token Generation Functions
        async function generateToken() {
            const deviceUuid = document.getElementById('deviceUuidInput').value.trim();
            const tokenError = document.getElementById('tokenError');
            const tokenResult = document.getElementById('tokenResult');
            const generatedToken = document.getElementById('generatedToken');
            
            // Hide previous messages
            tokenError.style.display = 'none';
            tokenResult.style.display = 'none';
            
            if (!deviceUuid) {
                tokenError.textContent = 'Please enter device UUID';
                tokenError.style.display = 'block';
                return;
            }
            
            // Validate UUID format
            const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
            if (!uuidRegex.test(deviceUuid)) {
                tokenError.textContent = 'Invalid UUID format';
                tokenError.style.display = 'block';
                return;
            }
            
            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        uuid: deviceUuid
                    })
                });
                
                const data = await response.json();
                
                if (response.ok && data.status === 'success') {
                    generatedToken.value = data.token;
                    tokenResult.style.display = 'block';
                } else {
                    tokenError.textContent = data.error || 'Не удалось сгенерировать токен';
                    tokenError.style.display = 'block';
                }
            } catch (error) {
                tokenError.textContent = `Ошибка: ${error.message}`;
                tokenError.style.display = 'block';
            }
        }
        
        function clearTokenForm() {
            document.getElementById('deviceUuidInput').value = '';
            document.getElementById('tokenError').style.display = 'none';
            document.getElementById('tokenResult').style.display = 'none';
            document.getElementById('tokenSuccess').style.display = 'none';
        }
        
        function copyToken() {
            const tokenInput = document.getElementById('generatedToken');
            tokenInput.select();
            tokenInput.setSelectionRange(0, 99999); // For mobile devices
            
            try {
                document.execCommand('copy');
                const tokenSuccess = document.getElementById('tokenSuccess');
                tokenSuccess.style.display = 'block';
                setTimeout(() => {
                    tokenSuccess.style.display = 'none';
                }, 2000);
            } catch (err) {
                console.error('Failed to copy token:', err);
            }
        }

        // Pending Connections Functions
        async function loadPendingConnections() {
            if (authSessionInvalid) {
                return;
            }
            const loadingEl = document.getElementById('pendingConnectionsLoading');
            const listEl = document.getElementById('pendingConnectionsList');
            const emptyEl = document.getElementById('pendingConnectionsEmpty');
            const tbody = document.getElementById('pendingConnectionsTableBody');
            
            try {
                loadingEl.style.display = 'block';
                listEl.style.display = 'none';
                emptyEl.style.display = 'none';
                
                const response = await fetch('/api/pending_connections', { headers: getAuthHeaders() });
                const data = await response.json();
                
                loadingEl.style.display = 'none';
                
                if (data.status === 'ok' && data.pending_connections && data.pending_connections.length > 0) {
                    tbody.innerHTML = '';
                    
                    data.pending_connections.forEach(conn => {
                        const row = document.createElement('tr');
                        
                        const ageMinutes = Math.floor(conn.age_seconds / 60);
                        const ageSeconds = Math.floor(conn.age_seconds % 60);
                        const ageText = ageMinutes > 0
                            ? `${ageMinutes}м ${ageSeconds}с назад`
                            : `${ageSeconds}с назад`;
                        
                        const reasonText = conn.reason === 'no_token'
                            ? 'Нет токена'
                            : conn.reason === 'invalid_token'
                            ? 'Неверный токен'
                            : 'Неизвестно';
                        
                        row.innerHTML = `
                            <td style="font-family: monospace; font-size: 12px;">${conn.device_id}</td>
                            <td>${ageText}</td>
                            <td><span class="status-badge status-pending">${reasonText}</span></td>
                            <td>${conn.ip_address || '—'}</td>
                            <td>
                                <button class="btn" style="padding: 4px 8px; font-size: 12px;" 
                                        onclick="useDeviceUuid('${conn.device_id}')">
                                    Использовать UUID
                                </button>
                            </td>
                        `;
                        tbody.appendChild(row);
                    });
                    
                    listEl.style.display = 'block';
                } else {
                    emptyEl.style.display = 'block';
                }
            } catch (error) {
                loadingEl.style.display = 'none';
                console.error('Error loading pending connections:', error);
            }
        }
        
        function useDeviceUuid(deviceUuid) {
            document.getElementById('deviceUuidInput').value = deviceUuid;
            document.getElementById('deviceUuidInput').scrollIntoView({ behavior: 'smooth', block: 'center' });
            document.getElementById('deviceUuidInput').focus();
        }

        async function loadConnectionPolicy() {
            try {
                const r = await fetch('/api/admin/connection_policy', { headers: getAuthHeaders() });
                const data = await r.json();
                if (data.policy) {
                    const radio = document.querySelector('input[name="connectionPolicy"][value="' + data.policy + '"]');
                    if (radio) radio.checked = true;
                }
            } catch (e) { console.error('loadConnectionPolicy:', e); }
        }

        async function loadConnectionRequests() {
            const loadingEl = document.getElementById('connectionRequestsLoading');
            const emptyEl = document.getElementById('connectionRequestsEmpty');
            const listEl = document.getElementById('connectionRequestsList');
            const tbody = document.getElementById('connectionRequestsTableBody');
            if (!tbody) return;
            if (loadingEl) loadingEl.style.display = 'block';
            if (emptyEl) emptyEl.style.display = 'none';
            if (listEl) listEl.style.display = 'none';
            try {
                const r = await fetch('/api/admin/connection_requests', { headers: getAuthHeaders() });
                const data = await r.json();
                if (loadingEl) loadingEl.style.display = 'none';
                const requests = (data.connection_requests || []);
                if (requests.length === 0) {
                    if (emptyEl) emptyEl.style.display = 'block';
                    return;
                }
                tbody.innerHTML = requests.map(req => {
                    const created = req.created_at ? new Date(req.created_at).toLocaleString('ru-RU') : '—';
                    const did = (req.device_id || '').replace(/"/g, '&quot;');
                    return '<tr><td style="font-family:monospace;font-size:12px;">' + (req.device_id || '') + '</td><td>' + (req.ip_address || '—') + '</td><td>' + (req.hostname || '—') + '</td><td>' + created + '</td><td><button type="button" class="btn btn-success btn-sm connection-request-approve" data-device-id="' + did + '">Одобрить</button> <button type="button" class="btn btn-danger btn-sm connection-request-reject" data-device-id="' + did + '">Отклонить</button></td></tr>';
                }).join('');
                if (listEl) listEl.style.display = 'block';
                document.querySelectorAll('.connection-request-approve').forEach(btn => {
                    btn.addEventListener('click', function() { connectionRequestAction(this.getAttribute('data-device-id'), 'approve'); });
                });
                document.querySelectorAll('.connection-request-reject').forEach(btn => {
                    btn.addEventListener('click', function() { connectionRequestAction(this.getAttribute('data-device-id'), 'reject'); });
                });
            } catch (e) {
                if (loadingEl) loadingEl.style.display = 'none';
                if (emptyEl) { emptyEl.textContent = 'Ошибка загрузки'; emptyEl.style.display = 'block'; }
                console.error('loadConnectionRequests:', e);
            }
        }

        async function connectionRequestAction(deviceId, action) {
            if (!deviceId) return;
            const path = action === 'approve' ? 'approve' : 'reject';
            try {
                const r = await fetch('/api/admin/connection_requests/' + encodeURIComponent(deviceId) + '/' + path, {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({})
                });
                const data = await r.json();
                if (data.status === 'ok') {
                    loadConnectionRequests();
                } else {
                    alert(data.error || 'Ошибка');
                }
            } catch (e) {
                alert('Ошибка: ' + e.message);
            }
        }

        document.getElementById('connectionPolicySaveBtn')?.addEventListener('click', async function() {
            const selected = document.querySelector('input[name="connectionPolicy"]:checked');
            const policy = selected ? selected.value : 'manual';
            const statusEl = document.getElementById('connectionPolicyStatus');
            try {
                const r = await fetch('/api/admin/connection_policy', {
                    method: 'PATCH',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({ policy: policy })
                });
                const data = await r.json();
                if (statusEl) { statusEl.textContent = data.status === 'ok' ? 'Сохранено' : (data.error || ''); if (data.status === 'ok') setTimeout(function() { statusEl.textContent = ''; }, 2000); }
            } catch (e) {
                if (statusEl) statusEl.textContent = 'Ошибка: ' + e.message;
            }
        });

        // ============================================
        // Ticket Queue (Stage 10.1)
        // ============================================
        const QUEUE_LAYOUT_KEY = 'admin_queue_layout_v1';
        const QUEUE_POLL_INTERVAL_MS = 25000;
        const QUEUE_POLL_INTERVAL_WS_ACTIVE_MS = 60000;
        let queueState = { tickets: [], lastSync: null, wsConnected: false, canWrite: true, actorId: '', actorRole: '', subscribedTicketIds: new Set(), queueReloadLock: false };
        const STATUS_RU_TO_CANONICAL = { 'Новая': 'new', 'В очереди у оператора': 'triaged', 'В работе': 'in_progress', 'Ожидание ответа пользователя': 'waiting_on_user', 'Ожидание внешней стороны': 'waiting_on_vendor', 'Решена': 'resolved', 'Закрыта': 'closed' };
        const STATUS_CANONICAL_TO_RU = { 'new': 'Новая', 'triaged': 'В очереди у оператора', 'in_progress': 'В работе', 'waiting_on_user': 'Ожидание ответа пользователя', 'waiting_on_vendor': 'Ожидание внешней стороны', 'resolved': 'Решена', 'closed': 'Закрыта' };
        const PRIORITY_CLASS_TO_RU = { P0: 'Критический', P1: 'Высокий', P2: 'Средний', P3: 'Низкий' };
        let queueManageModalTicketId = null;
        let queueManageModalTicket = null;
        let queueManageAssignAvailable = true;
        let queuePollTimer = null;
        let queueWs = null;
        let queueReconnectAttempts = 0;
        let queueReconnectTimer = null;
        const QUEUE_WS_RECONNECT_BACKOFF_MS = [1000, 2000, 5000, 10000];
        let queueDebounceReloadTimer = null;
        const QUEUE_DEBOUNCE_RELOAD_MS = 400;

        let pendingAgentUpdateOperationId = null;
        let pendingAgentUpdateDeviceId = null;
        let agentUpdatesBulkRows = [];
        let agentUpdatesBulkStatus = {};
        let workbenchTicketId = null;
        let pendingCanaryOperationId = null;
        let confirmedCanaryOperationId = null;

        function setPendingAgentUpdateOperation(opId, deviceId) {
            pendingAgentUpdateOperationId = opId;
            pendingAgentUpdateDeviceId = deviceId;
        }

        function setBulkPendingOperations(ops) {
            agentUpdatesBulkRows = (ops || []).slice();
            agentUpdatesBulkStatus = {};
        }

        function agentUpdateOnOperationUpdated(data) {
            const opId = data.operation_id;
            const status = data.status;
            const errMsg = data.error && data.error.message ? data.error.message : (data.error && data.error.code ? data.error.code : '');
            if (pendingAgentUpdateOperationId && opId === pendingAgentUpdateOperationId) {
                const resultEl = document.getElementById('agentUpdatesResult');
                const resultContent = document.getElementById('agentUpdatesResultContent');
                if (resultEl && resultContent) {
                    resultEl.style.display = 'block';
                    if (status === 'succeeded') {
                        resultContent.innerHTML = '<p class="success-message">Успех. Агент перезапустится и подключится с новой версией.</p>';
                    } else {
                        resultContent.innerHTML = '<p class="error-message">Ошибка: ' + escapeHtml(errMsg || status || 'Неизвестно') + '</p>';
                    }
                }
                if (pendingAgentUpdateDeviceId && queueWs && queueWs.readyState === WebSocket.OPEN) {
                    try { queueWs.send(JSON.stringify({ type: 'unsubscribe_device', device_id: pendingAgentUpdateDeviceId })); } catch (e) {}
                }
                pendingAgentUpdateOperationId = null;
                pendingAgentUpdateDeviceId = null;
            }
            if (opId && agentUpdatesBulkRows.some(function(r) { return r.operation_id === opId; })) {
                agentUpdatesBulkStatus[opId] = { status: status, error_message: errMsg };
                renderAgentUpdatesBulkResult();
            }
            if (pendingCanaryOperationId && opId === pendingCanaryOperationId && status === 'succeeded') {
                const canaryConfirmedEl = document.getElementById('agentUpdatesCanaryConfirmed');
                if (canaryConfirmedEl) canaryConfirmedEl.checked = true;
                confirmedCanaryOperationId = opId;
                pendingCanaryOperationId = null;
            }
        }

        function renderAgentUpdatesBulkResult() {
            const container = document.getElementById('agentUpdatesBulkResultContent');
            if (!container) return;
            let html = '';
            agentUpdatesBulkRows.forEach(function(r) {
                const entry = agentUpdatesBulkStatus[r.operation_id];
                const status = entry ? entry.status : 'pending';
                const err = entry ? entry.error_message : '';
                const buildStr = r.build ? (r.build.target + ' / ' + r.build.version) : ((r.target || '—') + ' / ' + (r.channel || '—'));
                let statusHtml = '<span class="badge badge-secondary">Ожидание...</span>';
                if (status === 'succeeded') statusHtml = '<span class="badge badge-success">Успех</span>';
                else if (status === 'failed') statusHtml = '<span class="badge badge-danger">Ошибка</span> ' + escapeHtml(err);
                html += '<div style="margin-bottom: 6px;"><code>' + escapeHtml((r.device_id || '').slice(0, 8)) + '...</code> ' + buildStr + ' — ' + statusHtml + '</div>';
            });
            container.innerHTML = html || '<p class="muted">Нет записей.</p>';
        }

        function queueStatusLabel(status) {
            return STATUS_CANONICAL_TO_RU[status] || status || 'Не указан';
        }

        function queueStatusClass(status) {
            return String(status || 'unknown').replace(/[_\s]+/g, '-').toLowerCase();
        }

        function queuePriorityClass(ticket) {
            return ticket.priority_class || 'P3';
        }

        function queuePriorityLabel(ticket) {
            const priorityClass = queuePriorityClass(ticket);
            const ru = PRIORITY_CLASS_TO_RU[priorityClass] || priorityClass;
            return `${ru} (${priorityClass})`;
        }

        function queueActionMarker(ticket) {
            if (ticket.requires_operator_action) return { cls: 'needs-action', text: 'Требует действия' };
            if ((ticket.status || '').startsWith('waiting_')) return { cls: 'waiting', text: 'Ожидание' };
            return null;
        }

        function queueUnreadSummary(ticket) {
            const counters = ticket.chat_counters || {};
            const unreadUser = Math.max(
                Number(counters.support_unread_user_messages || 0),
                Number(counters.support_pending_user_messages || 0),
            );
            if (!unreadUser) return '';
            const preview = String(counters.last_user_message_text || '').trim();
            const previewHtml = preview
                ? `<div class="queue-last-user-preview" title="${escapeHtml(preview)}">${escapeHtml(preview.slice(0, 96))}</div>`
                : '';
            return `<div class="queue-ticket-badges">
  <span class="queue-pill queue-pill-danger" title="Новые сообщения пользователя">${unreadUser}</span>
  ${previewHtml}
</div>`;
        }

        function getQueueLayoutKey() {
            const actorId = queueState.actorId || localStorage.getItem('admin_user_login') || 'default';
            return QUEUE_LAYOUT_KEY + ':' + actorId;
        }

        function queueLayoutLoad() {
            try {
                const raw = localStorage.getItem(getQueueLayoutKey());
                if (!raw) return { pinned_top: [], manual_rank: {}, compact: false, updated_at: '' };
                const data = JSON.parse(raw);
                return {
                    pinned_top: Array.isArray(data.pinned_top) ? data.pinned_top : [],
                    manual_rank: data.manual_rank && typeof data.manual_rank === 'object' ? data.manual_rank : {},
                    compact: !!data.compact,
                    updated_at: data.updated_at || ''
                };
            } catch (e) {
                return { pinned_top: [], manual_rank: {}, compact: false, updated_at: '' };
            }
        }

        function queueLayoutSave(layout) {
            try {
                layout.updated_at = new Date().toISOString();
                localStorage.setItem(getQueueLayoutKey(), JSON.stringify(layout));
            } catch (e) { console.warn('queueLayoutSave', e); }
        }

        function queueApplyOrder(tickets) {
            if (!tickets || tickets.length === 0) return tickets;
            const layout = queueLayoutLoad();
            const pinnedSet = new Set(layout.pinned_top);
            const rank = layout.manual_rank || {};
            const baseSort = (a, b) => {
                const pa = Number(a.effective_priority || 0);
                const pb = Number(b.effective_priority || 0);
                if (pa !== pb) return pb - pa;
                const ta = new Date(a.created_at || 0).getTime();
                const tb = new Date(b.created_at || 0).getTime();
                return ta - tb;
            };
            const pinned = tickets.filter(t => pinnedSet.has(t.ticket_id));
            const rest = tickets.filter(t => !pinnedSet.has(t.ticket_id));
            const sortByRank = (list, useRank) => {
                return list.slice().sort((a, b) => {
                    if (useRank) {
                        const ra = rank[a.ticket_id];
                        const rb = rank[b.ticket_id];
                        if (ra != null && rb != null) return ra - rb;
                        if (ra != null) return -1;
                        if (rb != null) return 1;
                    }
                    return baseSort(a, b);
                });
            };
            return [...sortByRank(pinned, true), ...sortByRank(rest, true)];
        }

        function queueBuildParams() {
            const q = new URLSearchParams();
            const search = document.getElementById('queueSearch')?.value?.trim();
            if (search) q.set('ticket_code', search);
            const queueId = document.getElementById('filterQueue')?.value;
            if (queueId) q.set('queue_id', queueId);
            const status = document.getElementById('filterStatus')?.value;
            if (status) q.set('status', status);
            const assignee = document.getElementById('filterAssignee')?.value;
            if (assignee) q.set('assignee_id', assignee);
            if (document.getElementById('filterUnassigned')?.checked) q.set('unassigned', 'true');
            if (document.getElementById('filterFrBreached')?.checked) q.set('first_response_breached', 'true');
            if (document.getElementById('filterResBreached')?.checked) q.set('resolution_breached', 'true');
            if (document.getElementById('filterWatching')?.checked && queueState.actorId) q.set('watching_actor_id', queueState.actorId);
            return q.toString();
        }

        function queueFormatAge(createdAt) {
            if (!createdAt) return '-';
            const d = new Date(createdAt);
            const sec = Math.floor((Date.now() - d) / 1000);
            if (sec < 60) return sec + 's';
            if (sec < 3600) return Math.floor(sec / 60) + 'm';
            if (sec < 86400) return Math.floor(sec / 3600) + 'h';
            return Math.floor(sec / 86400) + 'd';
        }

        function queueSlaShort(ticket) {
            const fr = ticket.first_response_breached_at ? 'breach' : (ticket.first_response_due_at ? 'due' : '-');
            const res = ticket.resolution_breached_at ? 'breach' : (ticket.resolution_due_at ? 'due' : '-');
            return { fr, res };
        }

        async function queueLoadTickets() {
            if (queueState.queueReloadLock) return;
            queueState.queueReloadLock = true;
            const wrapEl = document.getElementById('queueTableWrap');
            const savedScrollTop = wrapEl ? wrapEl.scrollTop : 0;
            const loadingEl = document.getElementById('queueTableLoading');
            const errorEl = document.getElementById('queueTableError');
            const tableEl = document.getElementById('queueTable');
            const emptyEl = document.getElementById('queueEmpty');
            if (loadingEl) loadingEl.style.display = 'block';
            if (errorEl) { errorEl.style.display = 'none'; errorEl.textContent = ''; }
            if (tableEl) tableEl.style.display = 'none';
            if (emptyEl) emptyEl.style.display = 'none';
            try {
                const query = queueBuildParams();
                const url = '/api/tickets' + (query ? '?' + query : '');
                const response = await fetch(url, { headers: getAuthHeaders() });
                const data = await response.json();
                if (loadingEl) loadingEl.style.display = 'none';
                if (data.status !== 'ok') {
                    if (errorEl) { errorEl.textContent = data.error || 'Ошибка загрузки тикетов'; errorEl.style.display = 'block'; }
                    return;
                }
                const raw = (data.tickets || []).map(t => t.ticket || t);
                queueState.tickets = raw;
                queueState.lastSync = new Date().toISOString();
                const layout = queueLayoutLoad();
                const compactEl = document.getElementById('queueCompactMode');
                if (compactEl) compactEl.checked = layout.compact;
                queueRenderTable();
                if (wrapEl) wrapEl.scrollTop = savedScrollTop;
                queueUpdateKpi();
                queueWsUpdateSubscriptions();
                document.getElementById('queueRowCount').textContent = raw.length + ' строк';
                document.getElementById('queueLastSync').textContent = 'Обновлено: ' + new Date().toLocaleTimeString();
            } catch (err) {
                if (loadingEl) loadingEl.style.display = 'none';
                if (errorEl) { errorEl.textContent = err.message || 'Ошибка сети'; errorEl.style.display = 'block'; }
            } finally {
                queueState.queueReloadLock = false;
            }
        }

        function queueUpdateKpi() {
            const t = queueState.tickets;
            const open = t.filter(x => x.status && !['resolved', 'closed'].includes(x.status)).length;
            const breached = t.filter(x => x.first_response_breached_at || x.resolution_breached_at).length;
            const unassigned = t.filter(x => !x.assignee_id).length;
            const elOpen = document.getElementById('kpiOpen'); if (elOpen) elOpen.innerHTML = 'Открыто: <strong>' + open + '</strong>';
            const elBreach = document.getElementById('kpiBreached'); if (elBreach) elBreach.innerHTML = 'SLA нарушен: <strong>' + breached + '</strong>';
            const elUn = document.getElementById('kpiUnassigned'); if (elUn) elUn.innerHTML = 'Без исполнителя: <strong>' + unassigned + '</strong>';
        }

        function queueFilteredTickets() {
            const priorityFilter = document.getElementById('filterPriority')?.value || '';
            const requesterFilter = (document.getElementById('filterRequester')?.value || '').trim().toLowerCase();
            return (queueState.tickets || []).filter((ticket) => {
                if (priorityFilter && queuePriorityClass(ticket) !== priorityFilter) return false;
                if (requesterFilter) {
                    const requesterText = String(ticket.requester_display_name || ticket.requester_id || '').toLowerCase();
                    if (!requesterText.includes(requesterFilter)) return false;
                }
                return true;
            });
        }

        function queueRenderTable() {
            const tbody = document.getElementById('queueTableBody');
            const tableEl = document.getElementById('queueTable');
            const emptyEl = document.getElementById('queueEmpty');
            if (!tbody) return;
            queueApplySingleModeUi();
            const sorted = queueApplyOrder(queueFilteredTickets());
            const compact = document.getElementById('queueCompactMode')?.checked;
            if (tableEl) { tableEl.classList.toggle('compact', !!compact); tableEl.style.display = sorted.length ? 'table' : 'none'; }
            if (emptyEl) emptyEl.style.display = sorted.length ? 'none' : 'block';
            const canWrite = queueState.canWrite;
            const layout = queueLayoutLoad();
            const pinnedSet = new Set(layout.pinned_top);
            const rank = layout.manual_rank || {};
            const hasLocalOrder = layout.pinned_top.length > 0 || Object.keys(rank).length > 0;
            const isClosed = (t) => (t.status || '').toLowerCase() === 'closed';
            tbody.innerHTML = sorted.map((t, idx) => {
                const code = t.ticket_code || t.ticket_id?.slice(0,8) || '-';
                const statusClass = queueStatusClass(t.status);
                const priorityClass = queuePriorityClass(t).toLowerCase();
                const marker = queueActionMarker(t);
                const markerHtml = marker ? `<div class="queue-action-marker ${marker.cls}">${marker.text}</div>` : '';
                const unreadSummaryHtml = queueUnreadSummary(t);
                const isPinned = pinnedSet.has(t.ticket_id);
                const canTakeSelf = canWrite && !!queueState.actorId && !t.assignee_id && t.status === 'new';
                const takeSelfBtn = canTakeSelf
                    ? `<button type="button" class="btn btn-sm btn-success" onclick="queueTakeSelf('${t.ticket_id}')" title="Назначить заявку на себя">Взять себе</button>`
                    : '';
                const actions = canWrite ? `
                    <div class="queue-actions-inline">
                        ${takeSelfBtn}
                        <button type="button" class="btn btn-sm btn-primary" onclick="queueActionOpenManage('${t.ticket_id}')" title="Статус, назначение, профиль инициатора">Управление</button>
                        <button type="button" class="btn btn-sm" onclick="queueOpenWorkbench('${t.ticket_id}')">Открыть</button>
                    </div>
                ` : '<button type="button" class="btn btn-sm" onclick="queueOpenWorkbench(\'' + t.ticket_id + '\')">Открыть</button>';
                const closedAttr = isClosed(t) ? ' data-queue-closed="1"' : '';
                return `<tr data-ticket-id="${t.ticket_id}" data-queue-id="${t.queue_id || ''}"${closedAttr}>
                    <td class="col-select">${canWrite ? `<input type="checkbox" class="queue-row-cb" value="${t.ticket_id}" data-closed="${isClosed(t) ? '1' : '0'}">` : ''}</td>
                    <td class="col-drag">${canWrite ? '<span class="queue-drag-handle" draggable="true" title="Перетащите для изменения порядка">⋮⋮</span>' : ''}</td>
                    <td class="col-pin"><button type="button" class="pin-btn ${isPinned ? 'pinned' : ''}" data-ticket-id="${t.ticket_id}" title="${isPinned ? 'Открепить' : 'Закрепить'}">${isPinned ? '📌' : '📄'}</button></td>
                    <td class="col-ticket"><a href="#" onclick="queueOpenWorkbench('${t.ticket_id}'); return false;">${code}</a></td>
                    <td class="col-title" title="${(t.title || '').replace(/"/g, '&quot;')}">${(t.title || '-').slice(0, 40)}${(t.title || '').length > 40 ? '…' : ''}</td>
                    <td class="col-queue">${t.queue_code || t.queue_id || '-'}</td>
                    <td class="col-status"><span class="badge-status status-${statusClass}">${queueStatusLabel(t.status)}</span>${markerHtml}</td>
                    <td class="col-priority"><span class="badge-priority priority-${priorityClass}">${queuePriorityLabel(t)}</span></td>
                    <td class="col-assignee">${t.assignee_id || '-'}</td>
                    <td class="col-requester">${t.requester_display_name || t.requester_id || '-'}${unreadSummaryHtml}</td>
                    <td class="col-created">${t.created_at ? new Date(t.created_at).toLocaleString() : '-'}</td>
                    <td class="col-age">${queueFormatAge(t.created_at)}</td>
                    <td class="col-actions">${actions}</td>
                </tr>`;
            }).join('');
            document.getElementById('queueLocalOrderActive')?.classList.toggle('hidden', !hasLocalOrder);
            const filterQueueId = document.getElementById('filterQueue')?.value || '';
            const hasSingleQueue = queueSingleMode() || (!!filterQueueId && queueState.tickets.length > 0);
            const anyManualRank = queueState.tickets.some(t => t.manual_rank != null);
            const badgeEl = document.getElementById('queueOrderModeBadge');
            const resetWrapEl = document.getElementById('queueOrderServerWrap');
            if (badgeEl) {
                if (hasSingleQueue && canWrite) {
                    badgeEl.textContent = anyManualRank ? 'РУЧНОЙ' : 'АВТО';
                    badgeEl.classList.remove('hidden');
                    badgeEl.classList.toggle('manual', !!anyManualRank);
                } else {
                    badgeEl.classList.add('hidden');
                }
            }
            if (resetWrapEl) {
                if (hasSingleQueue && canWrite) {
                    resetWrapEl.classList.remove('hidden');
                } else {
                    resetWrapEl.classList.add('hidden');
                }
            }
            queueBindPinButtons();
            queueBindQueueRowDrag();
            queueBindMassSelection();
        }

        function queueBindQueueRowDrag() {
            const tbody = document.getElementById('queueTableBody');
            if (!tbody) return;
            let draggedRow = null;
            tbody.querySelectorAll('.queue-drag-handle').forEach(handle => {
                handle.addEventListener('dragstart', function(e) {
                    const tr = e.target.closest('tr');
                    if (!tr) return;
                    draggedRow = tr;
                    e.dataTransfer.effectAllowed = 'move';
                    e.dataTransfer.setData('text/plain', tr.dataset.ticketId || '');
                    tr.classList.add('queue-drag-dragging');
                });
                handle.addEventListener('dragend', function(e) {
                    const tr = e.target.closest('tr');
                    if (tr) tr.classList.remove('queue-drag-dragging');
                    draggedRow = null;
                });
            });
            tbody.querySelectorAll('tr[data-ticket-id]').forEach(row => {
                row.addEventListener('dragover', function(e) {
                    e.preventDefault();
                    if (!draggedRow || draggedRow === this) return;
                    const rect = this.getBoundingClientRect();
                    const mid = rect.top + rect.height / 2;
                    this.classList.toggle('queue-drag-over-bottom', e.clientY >= mid);
                    this.classList.toggle('queue-drag-over-top', e.clientY < mid);
                });
                row.addEventListener('dragleave', function() {
                    this.classList.remove('queue-drag-over-top', 'queue-drag-over-bottom');
                });
                row.addEventListener('drop', function(e) {
                    e.preventDefault();
                    this.classList.remove('queue-drag-over-top', 'queue-drag-over-bottom');
                    if (!draggedRow || draggedRow === this) return;
                    const ticketId = draggedRow.dataset.ticketId;
                    const targetId = this.dataset.ticketId;
                    if (!ticketId || !targetId || ticketId === targetId) return;
                    const sorted = queueApplyOrder(queueFilteredTickets());
                    const fromIdx = sorted.findIndex(t => t.ticket_id === ticketId);
                    const toIdx = sorted.findIndex(t => t.ticket_id === targetId);
                    if (fromIdx < 0 || toIdx < 0) return;
                    const layout = queueLayoutLoad();
                    const rank = layout.manual_rank || {};
                    const myRank = rank[ticketId] != null ? rank[ticketId] : fromIdx;
                    const targetRank = rank[targetId] != null ? rank[targetId] : toIdx;
                    rank[ticketId] = targetRank;
                    rank[targetId] = myRank;
                    layout.manual_rank = rank;
                    queueLayoutSave(layout);
                    queueRenderTable();
                    const filterQueueId = document.getElementById('filterQueue')?.value || '';
                    const sameQueue = filterQueueId && draggedRow.dataset.queueId === filterQueueId;
                    if (sameQueue && typeof queueOrderServerMoveToPosition === 'function') {
                        queueOrderServerMoveToPosition(ticketId, fromIdx, toIdx);
                    }
                });
            });
        }

        function queueOpenWorkbench(ticketId) {
            const id = String(ticketId || '').trim();
            if (!id) return;
            workbenchTicketId = id;
            const label = document.getElementById('workbenchTicketLabel');
            const empty = document.getElementById('workbenchEmptyState');
            const frame = document.getElementById('workbenchFrame');
            if (label) label.textContent = 'Тикет: ' + id;
            if (empty) empty.style.display = 'none';
            if (frame) {
                frame.style.display = 'block';
                frame.src = '/ticket.html?ticket_id=' + encodeURIComponent(id);
            }
            switchTab('workbench');
        }

        async function queueOrderServerMoveToPosition(ticketId, fromIdx, toIdx) {
            if (fromIdx < 0 || fromIdx === toIdx) return;
            const direction = toIdx < fromIdx ? 'up' : 'down';
            const count = Math.abs(toIdx - fromIdx);
            for (let i = 0; i < count; i++) {
                try {
                    const res = await fetch('/api/tickets/' + ticketId + '/order', {
                        method: 'POST',
                        headers: getAuthHeaders(true),
                        body: JSON.stringify({ direction: direction })
                    });
                    const data = await res.json();
                    if (data.status !== 'ok') break;
                } catch (e) { break; }
            }
            queueLoadTickets();
        }

        function queueBindMassSelection() {
            const selectAll = document.getElementById('queueSelectAll');
            const massBar = document.getElementById('queueMassActionsBar');
            const countEl = document.getElementById('queueMassSelectedCount');
            const deselectBtn = document.getElementById('queueMassDeselect');
            const archiveBtn = document.getElementById('queueMassArchive');
            const assignSelect = document.getElementById('queueMassAssignSelect');
            const assignBtn = document.getElementById('queueMassAssignBtn');
            function updateMassBar() {
                const checked = document.querySelectorAll('.queue-row-cb:checked');
                const n = checked.length;
                if (massBar) massBar.style.display = n ? 'flex' : 'none';
                if (countEl) countEl.textContent = 'Выбрано: ' + n;
            }
            if (selectAll) {
                selectAll.onclick = function() {
                    const checked = this.checked;
                    document.querySelectorAll('.queue-row-cb').forEach(cb => { cb.checked = checked; });
                    updateMassBar();
                };
            }
            document.addEventListener('change', function(e) {
                if (e.target && e.target.classList && e.target.classList.contains('queue-row-cb')) updateMassBar();
            });
            if (deselectBtn) deselectBtn.addEventListener('click', function() {
                const sa = document.getElementById('queueSelectAll'); if (sa) sa.checked = false;
                document.querySelectorAll('.queue-row-cb').forEach(cb => { cb.checked = false; });
                updateMassBar();
            });
            if (archiveBtn) archiveBtn.addEventListener('click', queueMassArchive);
            if (assignBtn && assignSelect) assignBtn.addEventListener('click', () => queueMassAssign(assignSelect));
            queueFillMassAssignSelect();
            updateMassBar();
        }

        function queueFillMassAssignSelect() {
            const assignSelect = document.getElementById('queueMassAssignSelect');
            if (!assignSelect || !queueCachedUsers || !queueCachedUsers.length) return;
            const assignable = queueCachedUsers.filter(u => (u.actor_role === 'support' || u.actor_role === 'admin') && u.is_active !== false);
            assignSelect.innerHTML = '<option value="">Исполнитель...</option>' + assignable.map(u => `<option value="${(u.user_login || u.login || '').replace(/"/g, '&quot;')}">${(u.user_login || u.login || '').replace(/</g, '&lt;')}</option>`).join('');
        }

        async function queueMassArchive() {
            const closed = Array.from(document.querySelectorAll('.queue-row-cb:checked[data-closed="1"]')).map(cb => cb.value);
            if (closed.length === 0) { queueToast('Выберите только закрытые тикеты', true); return; }
            try {
                const res = await fetch('/api/tickets/archive', {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({ ticket_ids: closed })
                });
                const data = await responseToJson(res);
                if (data.status === 'ok') {
                    queueToast('Тикеты отправлены в архив');
                    document.querySelectorAll('.queue-row-cb:checked').forEach(cb => { cb.checked = false; });
                    document.getElementById('queueSelectAll') && (document.getElementById('queueSelectAll').checked = false);
                    queueLoadTickets();
                } else { queueToast(data.error || 'Ошибка', true); }
            } catch (e) { queueToast(e.message, true); }
        }

        async function queueMassAssign(selectEl) {
            const assigneeId = (selectEl && selectEl.value) || '';
            if (!assigneeId) { queueToast('Выберите исполнителя', true); return; }
            const nonClosed = Array.from(document.querySelectorAll('.queue-row-cb:checked[data-closed="0"]')).map(cb => cb.value);
            if (nonClosed.length === 0) { queueToast('Выберите тикеты (не закрытые)', true); return; }
            if (nonClosed.length > 3) { queueToast('Максимум 3 тикета для массового назначения', true); return; }
            try {
                const res = await fetch('/api/tickets/bulk_assign', {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({ ticket_ids: nonClosed, assignee_id: assigneeId })
                });
                const data = await responseToJson(res);
                if (data.status === 'ok') {
                    queueToast('Исполнитель назначен');
                    document.querySelectorAll('.queue-row-cb:checked').forEach(cb => { cb.checked = false; });
                    document.getElementById('queueSelectAll') && (document.getElementById('queueSelectAll').checked = false);
                    queueLoadTickets();
                } else { queueToast(data.error || 'Ошибка', true); }
            } catch (e) { queueToast(e.message, true); }
        }

        function queueBindPinButtons() {
            document.querySelectorAll('.queue-table .pin-btn').forEach(btn => {
                btn.removeEventListener('click', queueHandlePinClick);
                btn.addEventListener('click', queueHandlePinClick);
            });
        }

        function queueHandlePinClick(ev) {
            const ticketId = ev.target.closest('.pin-btn')?.dataset?.ticketId;
            if (!ticketId) return;
            const layout = queueLayoutLoad();
            const idx = layout.pinned_top.indexOf(ticketId);
            if (idx >= 0) layout.pinned_top.splice(idx, 1);
            else layout.pinned_top.push(ticketId);
            queueLayoutSave(layout);
            queueRenderTable();
        }

        function queueMoveRow(ticketId, delta) {
            const layout = queueLayoutLoad();
            const sorted = queueApplyOrder(queueState.tickets);
            const idx = sorted.findIndex(t => t.ticket_id === ticketId);
            if (idx < 0) return;
            const swapIdx = delta < 0 ? idx - 1 : idx + 1;
            if (swapIdx < 0 || swapIdx >= sorted.length) return;
            const rank = layout.manual_rank || {};
            const myRank = rank[ticketId] != null ? rank[ticketId] : idx;
            const other = sorted[swapIdx];
            const otherRank = rank[other.ticket_id] != null ? rank[other.ticket_id] : swapIdx;
            rank[ticketId] = otherRank;
            rank[other.ticket_id] = myRank;
            layout.manual_rank = rank;
            queueLayoutSave(layout);
            queueRenderTable();
        }

        function queueLayoutReset() {
            const layout = { pinned_top: [], manual_rank: {}, compact: !!document.getElementById('queueCompactMode')?.checked, updated_at: '' };
            queueLayoutSave(layout);
            queueLoadTickets();
        }

        async function queueOrderServer(ticketId, direction) {
            try {
                const res = await fetch('/api/tickets/' + ticketId + '/order', {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({ direction: direction })
                });
                const data = await res.json();
                if (data.status === 'ok') { queueToast('Порядок обновлён'); queueLoadTickets(); }
                else { queueToast(data.error || 'Ошибка', true); if (res.status === 403) queueState.canWrite = false; }
            } catch (e) { queueToast(e.message, true); }
        }

        async function queueOrderResetServer() {
            const queueId = document.getElementById('filterQueue')?.value;
            if (!queueId) { queueToast('Выберите одну очередь', true); return; }
            if (!confirm('Сбросить ручной порядок очереди? Позиции будут пересчитаны по приоритету и SLA.')) return;
            try {
                const res = await fetch('/api/tickets/queues/' + queueId + '/order/reset', {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({})
                });
                const data = await res.json();
                if (data.status === 'ok') { queueToast('Порядок сброшен'); queueLoadTickets(); }
                else { queueToast(data.error || 'Ошибка', true); if (res.status === 403) queueState.canWrite = false; }
            } catch (e) { queueToast(e.message, true); }
        }

        let queueCachedUsers = [];
        let queueCachedQueues = [];
        let queueCachedDevices = [];

        function queueSingleMode() {
            return (queueCachedQueues || []).length <= 1;
        }

        function queueApplySingleModeUi() {
            document.body.classList.toggle('queue-single-mode', queueSingleMode());
            const queueFilter = document.getElementById('filterQueue');
            if (queueSingleMode() && queueFilter && queueCachedQueues.length === 1) {
                queueFilter.value = String(queueCachedQueues[0].id);
            }
        }

        async function queueAssignSubmit(selectEl) {
            const ticketId = selectEl?.dataset?.ticketId;
            const assigneeId = selectEl?.value;
            if (!ticketId) return;
            try {
                const res = await fetch(`/api/tickets/${ticketId}/assign`, {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({ assignee_id: assigneeId === '' ? null : assigneeId })
                });
                const data = await res.json();
                if (data.status === 'ok') { queueToast('Исполнитель изменён'); queueLoadTickets(); }
                else { queueToast(data.error || 'Ошибка', true); if (res.status === 403) queueState.canWrite = false; }
            } catch (e) { queueToast(e.message, true); }
        }

        async function queueTakeSelf(ticketId) {
            if (!ticketId) return;
            if (!queueState.actorId) {
                queueToast('Не удалось определить текущего пользователя', true);
                return;
            }
            try {
                const res = await fetch(`/api/tickets/${ticketId}/assign`, {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({ assignee_id: queueState.actorId, take_self: true })
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    queueToast('Заявка назначена на вас');
                    queueLoadTickets();
                    return;
                }
                queueToast(data.message || data.error || 'Ошибка', true);
                if (res.status === 403) queueState.canWrite = false;
            } catch (e) {
                queueToast(e.message, true);
            }
        }

        function queueManageModalClose() {
            const overlay = document.getElementById('queueManageModalOverlay');
            if (overlay) overlay.style.display = 'none';
            queueManageModalTicketId = null;
            queueManageModalTicket = null;
        }

        function queueManageFillStatus(ticket) {
            const sel = document.getElementById('queueManageStatus');
            if (!sel) return;
            const canonical = ticket?.status || 'new';
            const opts = Object.entries(STATUS_CANONICAL_TO_RU)
                .filter(([can]) => can !== 'closed')
                .map(([can, ru]) => `<option value="${can}"${canonical === can ? ' selected' : ''}>${ru}</option>`);
            sel.innerHTML = opts.length ? opts.join('') : '<option value="new">Новая</option>';
        }

        function queueManageFillAssign(ticket) {
            const wrap = document.getElementById('queueManageAssignWrap');
            const sel = document.getElementById('queueManageAssign');
            const degraded = document.getElementById('queueManageAssignDegraded');
            const autoBtn = document.getElementById('queueManageAssignAuto');
            const isSupport = queueState.actorRole === 'support';
            if (autoBtn) autoBtn.style.display = isSupport ? 'none' : '';
            if (!sel) return;
            if (!queueManageAssignAvailable || !queueCachedUsers.length) {
                if (degraded) degraded.style.display = 'block';
                if (wrap) wrap.style.display = 'none';
                document.getElementById('queueManageAssignApply')?.setAttribute('disabled', 'disabled');
                return;
            }
            if (degraded) degraded.style.display = 'none';
            if (wrap) wrap.style.display = '';
            document.getElementById('queueManageAssignApply')?.removeAttribute('disabled');
            const assigneeId = ticket?.assignee_id || '';
            const assignableUsers = queueCachedUsers.filter(u => (u.actor_role === 'support' || u.actor_role === 'admin') && u.is_active !== false);
            if (isSupport) {
                const selfLogin = queueState.actorId || '';
                if (!selfLogin) {
                    if (degraded) degraded.style.display = 'block';
                    if (wrap) wrap.style.display = 'none';
                    document.getElementById('queueManageAssignApply')?.setAttribute('disabled', 'disabled');
                    return;
                }
                const selfUser = assignableUsers.find(u => (u.user_login || '') === selfLogin);
                const activeCount = Number(selfUser?.active_count || 0);
                const suffix = ` [активных: ${activeCount}${selfUser?.assignment_available === false ? ', лимит' : ''}]`;
                sel.innerHTML = `<option value="${selfLogin}">${selfLogin}${suffix}</option>`;
                sel.value = selfLogin;
                return;
            }
            const opts = ['<option value="">Снять назначение</option>'].concat(assignableUsers.map(u => {
                const activeCount = Number(u.active_count || 0);
                const suffix = ` [активных: ${activeCount}${u.assignment_available === false ? ', лимит' : ''}]`;
                return `<option value="${u.user_login || ''}"${(u.user_login || '') === assigneeId ? ' selected' : ''}>${u.user_login || ''}${suffix}</option>`;
            }));
            sel.innerHTML = opts.join('');
        }

        function queueManageFillQueueAndPriority(ticket) {
            const qSel = document.getElementById('queueManageQueueId');
            const urgencySel = document.getElementById('queueManageUrgency');
            const urgencyReason = document.getElementById('queueManageUrgencyReason');
            const importanceSel = document.getElementById('queueManageImportance');
            const importanceReason = document.getElementById('queueManageImportanceReason');
            if (qSel && queueCachedQueues.length) {
                qSel.innerHTML = queueCachedQueues.map(q => `<option value="${q.id}"${(ticket?.queue_id != null && String(ticket.queue_id) === String(q.id)) ? ' selected' : ''}>${q.code || q.name || q.id}</option>`).join('');
            }
            if (urgencySel) urgencySel.value = String(Boolean(ticket?.urgency));
            if (importanceSel) importanceSel.value = String(Boolean(ticket?.importance));
            if (urgencyReason) urgencyReason.value = ticket?.urgency_reason || '';
            if (importanceReason) importanceReason.value = ticket?.importance_reason || '';
        }

        function queueManageFillRequester(ticket) {
            const profile = ticket?.requester_profile || {};
            const displayNameInput = document.getElementById('queueManageRequesterDisplayName');
            const fullNameInput = document.getElementById('queueManageRequesterFullName');
            const buildingInput = document.getElementById('queueManageRequesterBuilding');
            const roomInput = document.getElementById('queueManageRequesterRoom');
            const phoneInput = document.getElementById('queueManageRequesterPhone');
            if (displayNameInput) displayNameInput.value = ticket?.requester_display_name || '';
            if (fullNameInput) fullNameInput.value = profile.full_name || '';
            if (buildingInput) buildingInput.value = profile.building || '';
            if (roomInput) roomInput.value = profile.room || '';
            if (phoneInput) phoneInput.value = profile.phone || '';
        }

        function queueManageFillDevice(ticket) {
            const select = document.getElementById('queueManageDeviceId');
            if (!select) return;
            const current = ticket?.device_id || '';
            const options = ['<option value="">-- Выберите агент --</option>'].concat(
                (queueCachedDevices || []).map(device => {
                    const label = (device.hostname || device.device_id || 'device') + (device.online ? ' (online)' : ' (offline)');
                    return `<option value="${device.device_id}">${label}</option>`;
                })
            );
            select.innerHTML = options.join('');
            select.value = current && (queueCachedDevices || []).some(device => device.device_id === current) ? current : '';
        }

        async function queueActionOpenManage(ticketId) {
            queueManageModalTicketId = ticketId;
            const overlay = document.getElementById('queueManageModalOverlay');
            const codeEl = document.getElementById('queueManageModalTicketCode');
            if (!overlay) return;
            overlay.style.display = 'flex';
            document.getElementById('queueManageStatusError')?.style?.setProperty('display', 'none');
            document.getElementById('queueManageAssignError')?.style?.setProperty('display', 'none');
            document.getElementById('queueManageQueueError')?.style?.setProperty('display', 'none');
            const t = queueState.tickets.find(x => x.ticket_id === ticketId);
            if (t) {
                queueManageModalTicket = t;
                if (codeEl) codeEl.textContent = t.ticket_code || t.ticket_id?.slice(0, 8) || ticketId;
                queueManageFillStatus(t);
                queueManageFillQueueAndPriority(t);
                queueManageFillRequester(t);
            } else {
                queueManageModalTicket = null;
                if (codeEl) codeEl.textContent = ticketId.slice(0, 8);
                try {
                    const res = await fetch('/api/tickets/' + ticketId, { headers: getAuthHeaders() });
                    const data = await res.json();
                    if (data.ticket) {
                        queueManageModalTicket = data.ticket;
                        queueManageFillStatus(data.ticket);
                        queueManageFillQueueAndPriority(data.ticket);
                        queueManageFillRequester(data.ticket);
                    }
                } catch (e) {}
            }
            queueManageFillAssign(queueManageModalTicket || {});
            queueManageFillDevice(queueManageModalTicket || {});

            if (queueCachedQueues.length === 0) {
                try {
                    const r = await fetch('/api/admin/tickets/queues', { headers: getAuthHeaders() });
                    if (r.ok) {
                        const data = await r.json();
                        queueCachedQueues = data.queues || [];
                    } else {
                        queueCachedQueues = [];
                    }
                    queueManageFillQueueAndPriority(queueManageModalTicket || {});
                } catch (e) {
                    queueCachedQueues = [];
                    queueManageFillQueueAndPriority(queueManageModalTicket || {});
                }
            }
            if (queueCachedUsers.length === 0) {
                try {
                    const r = await fetch('/api/admin/users', { headers: getAuthHeaders() });
                    if (r.status === 403 || r.status === 404) {
                        queueManageAssignAvailable = false;
                        queueManageFillAssign(queueManageModalTicket || {});
                        return;
                    }
                    if (!r.ok) return;
                    const data = await r.json();
                    if (data.users) {
                        queueCachedUsers = data.users.filter(u => u.is_active !== false);
                        queueManageAssignAvailable = true;
                        queueManageFillAssign(queueManageModalTicket || {});
                    }
                } catch (e) {
                    queueManageAssignAvailable = false;
                    queueManageFillAssign(queueManageModalTicket || {});
                }
            }
            if (queueCachedDevices.length === 0) {
                try {
                    const r = await fetch('/api/devices', { headers: getAuthHeaders() });
                    if (r.ok) {
                        const data = await r.json();
                        queueCachedDevices = data.devices || [];
                    } else {
                        queueCachedDevices = [];
                    }
                } catch (e) {
                    queueCachedDevices = [];
                }
                queueManageFillDevice(queueManageModalTicket || {});
            }
        }

        async function queueManageStatusApply() {
            if (!queueManageModalTicketId) return;
            const canonical = document.getElementById('queueManageStatus')?.value;
            if (!canonical) return;
            const errEl = document.getElementById('queueManageStatusError');
            errEl.style.display = 'none';
            try {
                const res = await fetch(`/api/tickets/${queueManageModalTicketId}/status`, { method: 'POST', headers: getAuthHeaders(true), body: JSON.stringify({ to_status: canonical }) });
                const data = await res.json();
                if (res.status === 403) { queueState.canWrite = false; queueManageModalClose(); queueToast('Нет прав'); queueLoadTickets(); return; }
                if (data.status === 'ok') { queueToast('Статус изменён'); queueLoadTickets(); queueManageModalClose(); }
                else { errEl.textContent = data.error || data.invalid_transition || data.message || 'Ошибка'; errEl.style.display = 'inline'; }
            } catch (e) { errEl.textContent = e.message; errEl.style.display = 'inline'; }
        }

        async function queueManageAssignApply() {
            if (!queueManageModalTicketId || !queueManageAssignAvailable) return;
            const assigneeId = document.getElementById('queueManageAssign')?.value;
            const errEl = document.getElementById('queueManageAssignError');
            errEl.style.display = 'none';
            try {
                const res = await fetch(`/api/tickets/${queueManageModalTicketId}/assign`, { method: 'POST', headers: getAuthHeaders(true), body: JSON.stringify({ assignee_id: assigneeId === '' ? null : assigneeId }) });
                const data = await res.json();
                if (res.status === 403) { queueState.canWrite = false; queueManageModalClose(); queueToast('Нет прав'); queueLoadTickets(); return; }
                if (data.status === 'ok') { queueToast('Исполнитель изменён'); queueLoadTickets(); queueManageModalTicket = queueManageModalTicket || {}; queueManageModalTicket.assignee_id = assigneeId || null; }
                else { errEl.textContent = data.error || 'Ошибка'; errEl.style.display = 'inline'; }
            } catch (e) { errEl.textContent = e.message; errEl.style.display = 'inline'; }
        }

        async function queueManageAssignAuto() {
            if (!queueManageModalTicketId || !queueManageAssignAvailable) return;
            const errEl = document.getElementById('queueManageAssignError');
            errEl.style.display = 'none';
            try {
                const res = await fetch(`/api/tickets/${queueManageModalTicketId}/assign`, {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({ auto_assign: true, reason: 'auto_balance' })
                });
                const data = await res.json();
                if (res.status === 403) { queueState.canWrite = false; queueManageModalClose(); queueToast('Нет прав'); queueLoadTickets(); return; }
                if (data.status === 'ok') { queueToast(data.auto_assigned ? 'Тикет автоназначен' : 'Исполнитель изменён'); queueLoadTickets(); queueManageModalClose(); }
                else { errEl.textContent = data.message || data.error || 'Ошибка'; errEl.style.display = 'inline'; }
            } catch (e) { errEl.textContent = e.message; errEl.style.display = 'inline'; }
        }

        async function queueManageQueueApply() {
            if (!queueManageModalTicketId) return;
            const queueId = document.getElementById('queueManageQueueId')?.value;
            const reason = (document.getElementById('queueManageQueueReason')?.value || '').trim() || 'manual';
            const errEl = document.getElementById('queueManageQueueError');
            errEl.style.display = 'none';
            if (!queueId) { errEl.textContent = 'Выберите очередь'; errEl.style.display = 'inline'; return; }
            try {
                const res = await fetch(`/api/tickets/${queueManageModalTicketId}/queue`, { method: 'POST', headers: getAuthHeaders(true), body: JSON.stringify({ queue_id: parseInt(queueId, 10), reason: reason }) });
                const data = await res.json();
                if (res.status === 403) { queueState.canWrite = false; queueManageModalClose(); queueToast('Нет прав'); queueLoadTickets(); return; }
                if (data.status === 'ok') { queueToast('Очередь изменена'); queueLoadTickets(); queueManageModalClose(); }
                else { errEl.textContent = data.error || data.message || 'Ошибка'; errEl.style.display = 'inline'; }
            } catch (e) { errEl.textContent = e.message; errEl.style.display = 'inline'; }
        }

        async function queueManagePriorityApply() {
            if (!queueManageModalTicketId) return;
            const urgency = document.getElementById('queueManageUrgency')?.value === 'true';
            const urgencyReason = (document.getElementById('queueManageUrgencyReason')?.value || '').trim();
            const importance = document.getElementById('queueManageImportance')?.value === 'true';
            const importanceReason = (document.getElementById('queueManageImportanceReason')?.value || '').trim();
            const errEl = document.getElementById('queueManageQueueError');
            errEl.style.display = 'none';
            if (!urgencyReason || !importanceReason) {
                errEl.textContent = 'Заполните оба обоснования';
                errEl.style.display = 'inline';
                return;
            }
            try {
                const res = await fetch(`/api/tickets/${queueManageModalTicketId}/priority`, {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({
                        urgency: urgency,
                        importance: importance,
                        urgency_reason: urgencyReason,
                        importance_reason: importanceReason
                    })
                });
                const data = await res.json();
                if (res.status === 403) { queueState.canWrite = false; queueManageModalClose(); queueToast('Нет прав'); queueLoadTickets(); return; }
                if (data.status === 'ok') { queueToast('Приоритет пересчитан'); queueLoadTickets(); queueManageModalClose(); }
                else { errEl.textContent = data.error || 'Ошибка'; errEl.style.display = 'inline'; }
            } catch (e) { errEl.textContent = e.message; errEl.style.display = 'inline'; }
        }

        async function queueManageRequesterApply() {
            if (!queueManageModalTicketId) return;
            const errEl = document.getElementById('queueManageRequesterError');
            errEl.style.display = 'none';
            const payload = {
                user_display_name: document.getElementById('queueManageRequesterDisplayName')?.value || '',
                requester_profile: {
                    full_name: document.getElementById('queueManageRequesterFullName')?.value || '',
                    building: document.getElementById('queueManageRequesterBuilding')?.value || '',
                    room: document.getElementById('queueManageRequesterRoom')?.value || '',
                    phone: document.getElementById('queueManageRequesterPhone')?.value || ''
                }
            };
            try {
                const res = await fetch(`/api/tickets/${queueManageModalTicketId}/requester_profile`, {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (res.status === 403) { queueState.canWrite = false; queueManageModalClose(); queueToast('Нет прав'); queueLoadTickets(); return; }
                if (data.status === 'ok') { queueToast('Профиль инициатора сохранён'); queueLoadTickets(); queueManageModalClose(); }
                else { errEl.textContent = data.error || data.message || 'Ошибка'; errEl.style.display = 'inline'; }
            } catch (e) { errEl.textContent = e.message; errEl.style.display = 'inline'; }
        }

        async function queueManageRerouteClick() {
            if (!queueManageModalTicketId) return;
            if (!confirm('Выполнить перемаршрутизацию тикета? Очередь будет пересчитана по правилам маршрутизации.')) return;
            try {
                const res = await fetch(`/api/tickets/${queueManageModalTicketId}/reroute`, { method: 'POST', headers: getAuthHeaders(true), body: JSON.stringify({}) });
                const data = await res.json();
                if (res.status === 403) { queueState.canWrite = false; queueManageModalClose(); queueToast('Нет прав'); queueLoadTickets(); return; }
                if (data.status === 'ok') { queueToast('Перемаршрутизация выполнена'); queueLoadTickets(); queueManageModalClose(); }
                else { queueToast((data.error || data.message || 'Ошибка') + (data.details ? ' ' + JSON.stringify(data.details) : ''), true); }
            } catch (e) { queueToast('Сеть: ' + e.message, true); }
        }

        async function queueManageDeviceApply() {
            if (!queueManageModalTicketId) return;
            const deviceId = document.getElementById('queueManageDeviceId')?.value || '';
            const reason = (document.getElementById('queueManageDeviceReason')?.value || '').trim() || 'manual_bind';
            const errEl = document.getElementById('queueManageDeviceError');
            errEl.style.display = 'none';
            if (!deviceId) {
                errEl.textContent = 'Выберите агент';
                errEl.style.display = 'inline';
                return;
            }
            try {
                const res = await fetch(`/api/tickets/${queueManageModalTicketId}/device`, {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({ device_id: deviceId, reason: reason })
                });
                const data = await res.json();
                if (res.status === 403) { queueState.canWrite = false; queueManageModalClose(); queueToast('Нет прав'); queueLoadTickets(); return; }
                if (data.status === 'ok') { queueToast('Тикет привязан к агенту'); queueLoadTickets(); queueManageModalClose(); }
                else { errEl.textContent = data.error || data.message || 'Ошибка'; errEl.style.display = 'inline'; }
            } catch (e) {
                errEl.textContent = e.message;
                errEl.style.display = 'inline';
            }
        }

        function queueToast(message, isError) {
            const el = document.getElementById('queueToast');
            if (!el) return;
            el.textContent = message;
            el.className = 'queue-toast' + (isError ? ' error' : '');
            el.style.display = 'block';
            clearTimeout(queueToast._t);
            queueToast._t = setTimeout(() => { el.style.display = 'none'; }, 3000);
        }

        function queueInit() {
            queueState.actorId = localStorage.getItem('admin_user_login') || '';
            const role = localStorage.getItem('admin_actor_role') || '';
            queueState.actorRole = role;
            queueState.canWrite = role !== 'auditor';
            const layout = queueLayoutLoad();
            const compactEl = document.getElementById('queueCompactMode');
            if (compactEl) {
                compactEl.checked = layout.compact;
                compactEl.addEventListener('change', () => {
                    const l = queueLayoutLoad();
                    l.compact = compactEl.checked;
                    queueLayoutSave(l);
                    queueRenderTable();
                });
            }
            document.getElementById('queueRefreshBtn')?.addEventListener('click', () => queueLoadTickets());
            document.getElementById('queueResetLocalOrder')?.addEventListener('click', () => queueLayoutReset());
            document.getElementById('queueOrderResetBtn')?.addEventListener('click', () => queueOrderResetServer());
            document.getElementById('queueResetFilters')?.addEventListener('click', () => {
                document.getElementById('filterQueue').value = '';
                document.getElementById('filterStatus').value = '';
                document.getElementById('filterPriority').value = '';
                document.getElementById('filterAssignee').value = '';
                document.getElementById('filterRequester').value = '';
                document.getElementById('filterWatching').checked = false;
                document.getElementById('filterUnassigned').checked = false;
                document.getElementById('filterFrBreached').checked = false;
                document.getElementById('filterResBreached').checked = false;
                document.getElementById('queueSearch').value = '';
                queueLoadTickets();
            });
            document.getElementById('queueEmptyResetFilters')?.addEventListener('click', () => document.getElementById('queueResetFilters')?.click());
            let searchDebounce;
            document.getElementById('queueSearch')?.addEventListener('input', () => {
                clearTimeout(searchDebounce);
                searchDebounce = setTimeout(() => queueLoadTickets(), 400);
            });
            ['filterQueue','filterStatus','filterPriority','filterAssignee','filterUnassigned','filterFrBreached','filterResBreached','filterWatching'].forEach(id => {
                document.getElementById(id)?.addEventListener('change', () => queueLoadTickets());
            });
            document.getElementById('filterRequester')?.addEventListener('change', () => queueLoadTickets());
            document.getElementById('presetUnassigned')?.addEventListener('click', () => { document.getElementById('filterUnassigned').checked = true; queueLoadTickets(); });
            document.getElementById('presetMyQueue')?.addEventListener('click', () => {
                const login = localStorage.getItem('admin_user_login');
                if (login) { document.getElementById('filterAssignee').value = login; document.getElementById('filterUnassigned').checked = false; queueLoadTickets(); }
                else alert('Логин не найден');
            });
            document.getElementById('presetBreached')?.addEventListener('click', () => { document.getElementById('filterFrBreached').checked = true; document.getElementById('filterResBreached').checked = true; queueLoadTickets(); });
            document.getElementById('presetHighPriority')?.addEventListener('click', () => { document.getElementById('filterPriority').value = 'P0'; queueLoadTickets(); });
            // Populate status/priority dropdowns
            const statusOpts = ['new','triaged','in_progress','waiting_on_user','waiting_on_vendor','resolved','closed'];
            const selStatus = document.getElementById('filterStatus');
            if (selStatus && selStatus.options.length <= 1) { statusOpts.forEach(s => { const o = document.createElement('option'); o.value = s; o.textContent = queueStatusLabel(s); selStatus.appendChild(o); }); }
            const priorities = ['P0','P1','P2','P3'];
            const selPri = document.getElementById('filterPriority');
            if (selPri && selPri.options.length <= 1) { priorities.forEach(p => { const o = document.createElement('option'); o.value = p; o.textContent = `${PRIORITY_CLASS_TO_RU[p]} (${p})`; selPri.appendChild(o); }); }
            fetch('/api/admin/tickets/queues', { headers: getAuthHeaders() }).then(r => {
                if (!r.ok) { queueCachedQueues = []; return; }
                return r.json();
            }).then(data => {
                if (data) queueCachedQueues = data.queues || [];
                queueApplySingleModeUi();
                const sel = document.getElementById('filterQueue');
                if (!sel || sel.options.length > 1) return;
                queueCachedQueues.forEach(q => { const o = document.createElement('option'); o.value = q.id; o.textContent = q.code || q.name || q.id; sel.appendChild(o); });
                queueApplySingleModeUi();
            }).catch(() => { queueCachedQueues = []; });
            fetch('/api/admin/users', { headers: getAuthHeaders() }).then(r => {
                if (r.status === 403 || r.status === 404) return;
                return r.json();
            }).then(data => {
                if (data && data.users) {
                    queueCachedUsers = data.users.filter(u => u.is_active !== false);
                    queueFillMassAssignSelect();
                    if (document.getElementById('queueTableBody')?.innerHTML) queueRenderTable();
                }
            }).catch(() => {});
            document.getElementById('queueManageModalClose')?.addEventListener('click', queueManageModalClose);
            document.getElementById('queueManageModalOverlay')?.addEventListener('click', (e) => { if (e.target.id === 'queueManageModalOverlay') queueManageModalClose(); });
            document.getElementById('queueManageStatusApply')?.addEventListener('click', () => queueManageStatusApply());
            document.getElementById('queueManageAssignApply')?.addEventListener('click', () => queueManageAssignApply());
            document.getElementById('queueManageAssignAuto')?.addEventListener('click', () => queueManageAssignAuto());
            document.getElementById('queueManageQueueApply')?.addEventListener('click', () => queueManageQueueApply());
            document.getElementById('queueManagePriorityApply')?.addEventListener('click', () => queueManagePriorityApply());
            document.getElementById('queueManageDeviceApply')?.addEventListener('click', () => queueManageDeviceApply());
            document.getElementById('queueManageRequesterApply')?.addEventListener('click', () => queueManageRequesterApply());
            document.getElementById('queueManageRerouteBtn')?.addEventListener('click', () => queueManageRerouteClick());
            queueLoadTickets();
            queueWsConnect();
            queueStartPolling();
        }

        function queueStartPolling() {
            if (authSessionInvalid) {
                return;
            }
            queueStopPolling();
            const interval = queueState.wsConnected ? QUEUE_POLL_INTERVAL_WS_ACTIVE_MS : QUEUE_POLL_INTERVAL_MS;
            queuePollTimer = setInterval(() => {
                const tab = document.getElementById('tab-queue');
                if (tab && tab.classList.contains('active') && typeof queueLoadTickets === 'function')
                    queueLoadTickets();
            }, interval);
        }
        function queueStopPolling() {
            if (queuePollTimer) { clearInterval(queuePollTimer); queuePollTimer = null; }
        }

        function queueSetRealtimeIndicator(connected) {
            queueState.wsConnected = !!connected;
            const el = document.getElementById('realtimeIndicator');
            if (el) {
                el.textContent = connected ? '● Онлайн' : '○ Ограниченный режим';
                el.className = 'realtime-indicator' + (connected ? ' live' : ' degraded');
            }
            queueStartPolling();
        }

        function queueWsUpdateSubscriptions() {
            if (!queueWs || queueWs.readyState !== WebSocket.OPEN) return;
            const visible = new Set(Array.from(document.querySelectorAll('#queueTableBody tr[data-ticket-id]')).map(r => r.dataset.ticketId));
            const prev = queueState.subscribedTicketIds;
            const toAdd = [...visible].filter(id => !prev.has(id));
            const toRemove = [...prev].filter(id => !visible.has(id));
            const token = localStorage.getItem('admin_auth_token');
            if (!token) return;
            toAdd.forEach(ticketId => {
                queueWs.send(JSON.stringify({ type: 'subscribe_ticket', ticket_id: ticketId, since_event_id: 0 }));
                queueState.subscribedTicketIds.add(ticketId);
            });
            toRemove.forEach(ticketId => {
                queueWs.send(JSON.stringify({ type: 'unsubscribe_ticket', ticket_id: ticketId }));
                queueState.subscribedTicketIds.delete(ticketId);
            });
        }

        function queueScheduleReload(immediate, eventType) {
            const forceReload = ['status_changed', 'queue_changed', 'assignee_changed', 'sla_breached', 'routing_applied', 'priority_changed'].includes(eventType);
            if (forceReload) {
                if (queueDebounceReloadTimer) clearTimeout(queueDebounceReloadTimer);
                queueDebounceReloadTimer = null;
                queueLoadTickets();
                return;
            }
            if (queueState.queueReloadLock) return;
            if (queueDebounceReloadTimer) clearTimeout(queueDebounceReloadTimer);
            queueDebounceReloadTimer = setTimeout(() => {
                queueDebounceReloadTimer = null;
                queueLoadTickets();
            }, QUEUE_DEBOUNCE_RELOAD_MS);
        }

        function queueWsConnect() {
            if (authSessionInvalid) return;
            if (queueWs && (queueWs.readyState === WebSocket.OPEN || queueWs.readyState === WebSocket.CONNECTING)) return;
            const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
            const url = proto + '//' + location.host + '/ws_ui';
            try {
                queueWs = new WebSocket(url);
            } catch (e) {
                queueSetRealtimeIndicator(false);
                return;
            }
            queueWs.onopen = () => {
                queueReconnectAttempts = 0;
                const token = localStorage.getItem('admin_auth_token');
                if (!token || authSessionInvalid) { queueWs.close(); return; }
                queueWs.send(JSON.stringify({ type: 'ui_hello', token: token }));
            };
            queueWs.onmessage = (ev) => {
                try {
                    const data = JSON.parse(ev.data);
                    if (data.type === 'error' && (data.error === 'Invalid token' || data.error === 'Token required')) {
                        handleAuthFailure('Сессия панели истекла. Войдите заново.');
                        return;
                    }
                    if (data.type === 'ui_hello_ack') {
                        queueSetRealtimeIndicator(true);
                        queueWsUpdateSubscriptions();
                        return;
                    }
                    if (data.type === 'ticket_event_committed' && data.ticket_id && queueState.subscribedTicketIds.has(data.ticket_id)) {
                        queueScheduleReload(false, data.event_type);
                    }
                    if (data.type === 'operation_updated') {
                        if (typeof agentUpdateOnOperationUpdated === 'function') agentUpdateOnOperationUpdated(data);
                    }
                } catch (e) { console.warn('queue ws message', e); }
            };
            queueWs.onclose = (event) => {
                queueWs = null;
                queueState.subscribedTicketIds.clear();
                queueSetRealtimeIndicator(false);
                if (authSessionInvalid) {
                    return;
                }
                if (event && event.code === 4003) {
                    handleAuthFailure('Сессия панели истекла. Войдите заново.');
                    return;
                }
                const tab = document.getElementById('tab-queue');
                if (tab && tab.classList.contains('active')) {
                    const delay = QUEUE_WS_RECONNECT_BACKOFF_MS[Math.min(queueReconnectAttempts, QUEUE_WS_RECONNECT_BACKOFF_MS.length - 1)];
                    queueReconnectAttempts++;
                    queueReconnectTimer = setTimeout(() => {
                        queueReconnectTimer = null;
                        queueWsConnect();
                    }, delay);
                }
            };
            queueWs.onerror = () => { queueWs.close(); };
        }

        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'hidden') {
                if (queueWs && queueWs.readyState === WebSocket.OPEN) {
                    queueState.subscribedTicketIds.forEach(tid => {
                        try { queueWs.send(JSON.stringify({ type: 'unsubscribe_ticket', ticket_id: tid })); } catch (e) {}
                    });
                    queueState.subscribedTicketIds.clear();
                }
            } else if (document.visibilityState === 'visible') {
                const tab = document.getElementById('tab-queue');
                if (tab && tab.classList.contains('active') && queueWs?.readyState === WebSocket.OPEN)
                    queueWsUpdateSubscriptions();
            }
        });

        // ============================================
        // Tab Management
        // ============================================
        
        // Tab switching functionality
        document.addEventListener('DOMContentLoaded', function() {
            const tabLinks = document.querySelectorAll('.tab-link');
            tabLinks.forEach(link => {
                link.addEventListener('click', function(e) {
                    e.preventDefault();
                    const tabName = this.getAttribute('data-tab');
                    switchTab(tabName);
                });
            });
            initWorkbenchTab();
            initTechTab();
        });

        function switchTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Remove active class from all menu items
            document.querySelectorAll('.tab-link').forEach(link => {
                link.classList.remove('active');
            });
            
            // Show selected tab
            const selectedTab = document.getElementById(`tab-${tabName}`);
            if (selectedTab) {
                selectedTab.classList.add('active');
            }
            
            // Add active class to menu item
            const selectedLink = document.querySelector(`.tab-link[data-tab="${tabName}"]`);
            if (selectedLink) {
                selectedLink.classList.add('active');
            }
            
            // Load tab-specific data
            if (tabName === 'queue') {
                if (typeof queueInit === 'function' && !document.getElementById('queueTableBody')?.dataset?.inited) {
                    const body = document.getElementById('queueTableBody');
                    if (body) body.dataset.inited = '1';
                    queueInit();
                } else if (typeof queueLoadTickets === 'function') queueLoadTickets();
                queueStartPolling();
            } else {
                queueStopPolling();
            }
            if (tabName === 'devices') {
                loadDevicesList();
                devicesApplyHash();
                loadConnectionPolicy();
                loadConnectionRequests();
            } else             if (tabName === 'modules') {
                loadModulesTab();
                initRegistryModulesToggles();
            } else if (tabName === 'users') {
                loadUsersTab();
            } else if (tabName === 'agent-updates') {
                loadAgentUpdatesTab();
            } else if (tabName === 'tech') {
                loadTechPanel();
            } else if (tabName === 'workbench') {
                const frame = document.getElementById('workbenchFrame');
                const empty = document.getElementById('workbenchEmptyState');
                if (frame && workbenchTicketId) {
                    frame.style.display = 'block';
                    if (!frame.src || frame.src.indexOf('ticket_id=' + encodeURIComponent(workbenchTicketId)) === -1) {
                        frame.src = '/ticket.html?ticket_id=' + encodeURIComponent(workbenchTicketId);
                    }
                } else if (empty) {
                    empty.style.display = 'block';
                }
            }
            if (tabName !== 'tech' && techPollTimer) {
                clearInterval(techPollTimer);
                techPollTimer = null;
            }
        }

        function initWorkbenchTab() {
            const backBtn = document.getElementById('workbenchBackToQueueBtn');
            if (backBtn) backBtn.addEventListener('click', function() { switchTab('queue'); });
            const refreshBtn = document.getElementById('workbenchRefreshBtn');
            if (refreshBtn) refreshBtn.addEventListener('click', function() {
                const frame = document.getElementById('workbenchFrame');
                if (!frame || !workbenchTicketId) return;
                frame.src = '/ticket.html?ticket_id=' + encodeURIComponent(workbenchTicketId) + '&_ts=' + Date.now();
            });
        }

        let techPollTimer = null;
        let techSelectedDeviceId = null;
        let techDevicesCache = [];
        let techSelectedModules = [];
        let techAgentActionState = {
            deviceId: null,
            text: '',
        };
        let techContextMenuState = {
            itemType: null,
            itemId: null,
            relatedLogId: null,
        };

        function techStatusClass(kind) {
            if (kind === 'ok') return 'ok';
            if (kind === 'warn') return 'warn';
            if (kind === 'bad') return 'bad';
            return 'neutral';
        }

        function techPill(label, kind) {
            return `<span class="tech-pill ${techStatusClass(kind)}">${escapeHtml(label || '—')}</span>`;
        }

        function techFormatDate(iso) {
            if (!iso) return '—';
            try { return new Date(iso).toLocaleString('ru-RU'); } catch (e) { return iso; }
        }

        function techFormatRelative(iso) {
            if (!iso) return '—';
            const diffSec = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
            if (diffSec < 60) return `${diffSec} сек назад`;
            if (diffSec < 3600) return `${Math.floor(diffSec / 60)} мин назад`;
            if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} ч назад`;
            return `${Math.floor(diffSec / 86400)} дн назад`;
        }

        function techIsStale(lastSeenAt, thresholdSec = 300) {
            if (!lastSeenAt) return true;
            return ((Date.now() - new Date(lastSeenAt).getTime()) / 1000) > thresholdSec;
        }

        function techProvisioningLabel(summary) {
            const state = summary?.provisioning_state || '';
            const map = {
                active: 'Токен активен',
                unprovisioned: 'Ждёт токен',
                token_revoked: 'Токен отозван',
                reprovision_required: 'Нужна перепривязка',
            };
            return map[state] || 'Неизвестно';
        }

        function techProvisioningKind(summary) {
            const state = summary?.provisioning_state || '';
            if (state === 'active') return 'ok';
            if (state === 'unprovisioned') return 'warn';
            return 'bad';
        }

        function techUpdateLabel(summary) {
            const status = String(summary?.last_update_operation_status || '').trim().toLowerCase();
            const map = {
                queued: 'В очереди',
                sent: 'Команда отправлена',
                accepted: 'Агент принял',
                running: 'Обновление идёт',
                success: 'Успешно',
                failed: 'Ошибка',
                timed_out: 'Таймаут',
                canceled: 'Отменено',
            };
            if (!status) return 'Не запускалось';
            return map[status] || status;
        }

        function techUpdateKind(summary) {
            const status = String(summary?.last_update_operation_status || '').trim().toLowerCase();
            if (!status) return 'neutral';
            if (status === 'success') return 'ok';
            if (status === 'queued' || status === 'sent' || status === 'accepted' || status === 'running') return 'warn';
            return 'bad';
        }

        function techJsonPreview(value) {
            if (!value || (typeof value === 'object' && !Object.keys(value).length)) return '—';
            const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
            return text.length > 220 ? text.slice(0, 220) + '…' : text;
        }

        function techActionLabel(action) {
            const map = {
                get_status: 'Статус агента',
                get_history: 'История агента',
                list_tasks: 'Список задач',
                refresh_toolset: 'Обновить набор инструментов',
                sync_modules: 'Синхронизировать модули',
                reconcile: 'Сверить состояние модулей',
                verify_module: 'Проверить модуль',
            };
            return map[action] || action;
        }

        function techDetailLabel(key) {
            const map = {
                actor_id: 'Кто выполнил',
                actor_role: 'Роль',
                reason: 'Причина',
                error: 'Ошибка',
                error_code: 'Код ошибки',
                error_message: 'Текст ошибки',
                protocol_version: 'Версия протокола',
                hostname: 'Хост',
                ip_address: 'IP-адрес',
                stale_count: 'Количество неактивных',
                threshold_seconds: 'Порог, сек',
                pending_stale_count: 'Зависших заявок',
                last_request_at: 'Последний запрос',
                token_prefix: 'Префикс токена',
                user_login: 'Пользователь',
                event_type: 'Тип события',
                module_name: 'Модуль',
                version: 'Версия',
                status: 'Статус',
                state: 'Состояние',
                count: 'Количество',
                connection_id: 'Подключение',
                line: 'Строка',
                source: 'Источник',
            };
            return map[key] || key.replace(/_/g, ' ');
        }

        function techFormatDetailValue(key, value) {
            if (value == null || value === '') return '—';
            if (typeof value === 'boolean') return value ? 'Да' : 'Нет';
            if (typeof value === 'number') return String(value);
            if (typeof value === 'string') {
                if (/_at$/.test(key) || key === 'timestamp') {
                    return techFormatDate(value);
                }
                return value;
            }
            return JSON.stringify(value);
        }

        function techRenderDetails(details) {
            if (!details || typeof details !== 'object') {
                return '<span class="muted">—</span>';
            }
            const entries = Object.entries(details).filter(([key, value]) => key !== 'samples' && value != null && value !== '');
            if (!entries.length) {
                return '<span class="muted">—</span>';
            }
            return entries.map(([key, value]) => `<div><strong>${escapeHtml(techDetailLabel(key))}:</strong> ${escapeHtml(techFormatDetailValue(key, value))}</div>`).join('');
        }

        function techHumanizeActionError(action, message) {
            const label = techActionLabel(action);
            const raw = String(message || '').trim();
            if (!raw) return `Не удалось выполнить команду «${label}».`;
            if (/not connected/i.test(raw)) {
                return `Агент сейчас не подключен к серверу. Команду «${label}» выполнить нельзя.`;
            }
            if (/timed? out|timeout/i.test(raw)) {
                return `Агент не ответил вовремя на команду «${label}».`;
            }
            if (/unknown action/i.test(raw)) {
                return `Сервер не знает команду «${label}».`;
            }
            return raw;
        }

        function techSetActionState(deviceId, text) {
            techAgentActionState = {
                deviceId: deviceId || null,
                text: text || '',
            };
            const resultBox = document.getElementById('techAgentActionResult');
            if (resultBox && techSelectedDeviceId === deviceId) {
                resultBox.textContent = text || 'Нажмите одну из кнопок выше, чтобы получить живой ответ от агента.';
            }
        }

        function techEnsureContextMenu() {
            let menu = document.getElementById('techContextMenu');
            if (menu) return menu;
            menu = document.createElement('div');
            menu.id = 'techContextMenu';
            menu.className = 'tech-context-menu';
            menu.innerHTML = `
                <button type="button" class="tech-context-action" data-tech-context-action="dismiss">Удалить из панели</button>
            `;
            document.body.appendChild(menu);
            menu.addEventListener('click', async function(e) {
                e.stopPropagation();
                const action = e.target.closest('[data-tech-context-action]')?.getAttribute('data-tech-context-action');
                if (action !== 'dismiss' || !techContextMenuState.itemType || !techContextMenuState.itemId) return;
                try {
                    await techDismissPanelItem(
                        techContextMenuState.itemType,
                        techContextMenuState.itemId,
                        techContextMenuState.relatedLogId
                    );
                    techCloseContextMenu();
                } catch (err) {
                    alert((err && err.message) ? err.message : 'Не удалось удалить элемент из панели');
                }
            });
            return menu;
        }

        function techCloseContextMenu() {
            const menu = document.getElementById('techContextMenu');
            if (menu) menu.classList.remove('open');
            techContextMenuState = {
                itemType: null,
                itemId: null,
                relatedLogId: null,
            };
        }

        function techOpenContextMenu(target, itemType, itemId, relatedLogId) {
            if (!target || !itemType || !itemId) return;
            const menu = techEnsureContextMenu();
            const rect = target.getBoundingClientRect();
            menu.style.left = `${Math.min(rect.left + 12, window.innerWidth - 220)}px`;
            menu.style.top = `${Math.min(rect.bottom + 6, window.innerHeight - 80)}px`;
            menu.classList.add('open');
            techContextMenuState = {
                itemType,
                itemId,
                relatedLogId: relatedLogId || null,
            };
        }

        async function techDismissPanelItem(itemType, itemId, relatedLogId) {
            const response = await fetch('/api/admin/tech/dismiss', {
                method: 'POST',
                headers: getAuthHeaders(true),
                body: JSON.stringify({
                    item_type: itemType,
                    item_id: itemId,
                    related_log_id: relatedLogId || null,
                }),
            });
            const data = await responseToJson(response);
            if (!response.ok || data.status !== 'ok') {
                throw new Error(data.error || 'Не удалось удалить элемент из панели');
            }
            await loadTechPanel(true);
        }

        function initTechTab() {
            const refreshBtn = document.getElementById('techRefreshBtn');
            if (refreshBtn) refreshBtn.addEventListener('click', () => loadTechPanel(true));
            const lifecycleBtn = document.getElementById('techLoadLifecycleBtn');
            if (lifecycleBtn) lifecycleBtn.addEventListener('click', () => loadTechLifecycle());
            techEnsureContextMenu();
            const tabTech = document.getElementById('tab-tech');
            if (tabTech) {
                tabTech.addEventListener('click', function(e) {
                    const dismissTarget = e.target.closest('[data-tech-menu-item]');
                    if (dismissTarget && !e.target.closest('a')) {
                        e.preventDefault();
                        e.stopPropagation();
                        techOpenContextMenu(
                            dismissTarget,
                            dismissTarget.getAttribute('data-tech-item-type'),
                            dismissTarget.getAttribute('data-tech-item-id'),
                            dismissTarget.getAttribute('data-tech-related-log-id')
                        );
                        return;
                    }
                    const a = e.target.closest('a.tech-lifecycle-jump');
                    if (a) {
                        e.preventDefault();
                        const did = a.getAttribute('data-device-id');
                        if (did && typeof switchTab === 'function') {
                            switchTab('devices');
                            if (typeof setDeviceHash === 'function') setDeviceHash(did);
                            if (typeof devicesApplyHash === 'function') devicesApplyHash();
                        }
                        return;
                    }
                    const row = e.target.closest('tr[data-tech-device-id]');
                    if (row) {
                        e.preventDefault();
                        selectTechAgent(row.getAttribute('data-tech-device-id'));
                        return;
                    }
                    const actionBtn = e.target.closest('button[data-tech-action]');
                    if (actionBtn) {
                        e.preventDefault();
                        handleTechActionButton(actionBtn);
                    }
                });
            }
            document.addEventListener('click', function(e) {
                if (!e.target.closest('#techContextMenu')) {
                    techCloseContextMenu();
                }
            });
            window.addEventListener('resize', techCloseContextMenu);
            window.addEventListener('scroll', techCloseContextMenu, true);
        }

        async function loadTechPanel(force) {
            const isActive = document.getElementById('tab-tech')?.classList.contains('active');
            if (!isActive && !force) return;
            const headers = getAuthHeaders();
            try {
                const [overviewRes, alertsRes, logsRes, devicesRes, agentsAuditRes, usersAuditRes, stuckOpsRes] = await Promise.all([
                    fetch('/api/admin/tech/overview', { headers }),
                    fetch('/api/admin/tech/alerts', { headers }),
                    fetch('/api/admin/tech/logs?limit=50', { headers }),
                    fetch('/api/devices', { headers }),
                    fetch('/api/admin/tech/agents/audit?limit=50', { headers }),
                    fetch('/api/admin/tech/users/audit?limit=50', { headers }),
                    fetch('/api/admin/tech/operations/stuck', { headers }),
                ]);
                const overviewData = await responseToJson(overviewRes);
                const alertsData = await responseToJson(alertsRes);
                const logsData = await responseToJson(logsRes);
                const devicesData = await responseToJson(devicesRes);
                const agentsData = await responseToJson(agentsAuditRes);
                const usersData = await responseToJson(usersAuditRes);
                const stuckData = await responseToJson(stuckOpsRes);
                const overview = overviewData.overview || {};
                renderTechOverviewCards(overview);
                renderTechAlerts(alertsData.alerts || overview.alerts || []);
                renderTechProblemLogs(logsData.logs || overview.problem_logs || []);
                techDevicesCache = devicesData.devices || [];
                renderTechAgentsTable(techDevicesCache);
                renderTechAuditTable('techAgentsAuditTable', agentsData.events || [], 'agent');
                renderTechAuditTable('techUsersAuditTable', usersData.events || [], 'user');
                renderTechStuckOpsTable(stuckData.operations || []);
                if (!techSelectedDeviceId && techDevicesCache.length) {
                    const preferred = techDevicesCache.find(item => item.online) || techDevicesCache[0];
                    techSelectedDeviceId = preferred.device_id;
                } else if (techSelectedDeviceId && !techDevicesCache.some(item => item.device_id === techSelectedDeviceId)) {
                    techSelectedDeviceId = techDevicesCache[0]?.device_id || null;
                }
                if (techSelectedDeviceId) {
                    loadTechAgentDetail(techSelectedDeviceId);
                }
            } catch (e) {
                const shell = document.getElementById('techAgentDetailShell');
                if (shell) shell.innerHTML = `<div class="tech-agent-detail"><div class="error-message">Ошибка загрузки техпанели: ${escapeHtml(e.message || String(e))}</div></div>`;
            }
            if (techPollTimer) clearInterval(techPollTimer);
            techPollTimer = setInterval(() => {
                const active = document.getElementById('tab-tech')?.classList.contains('active');
                if (active) loadTechPanel(false);
            }, 10000);
        }

        function renderTechOverviewCards(overview) {
            const host = document.getElementById('techOverviewCards');
            if (!host) return;
            const pg = overview.postgres_health || {};
            const agent = overview.agent_health || {};
            const ops = overview.operations_health || {};
            const upd = overview.update_health || {};
            const svc = overview.service_health || {};
            const toStatusClass = (value) => {
                if (value === 'ok' || value === 0 || value === false) return 'health-green';
                if (value === 'down' || value === true) return 'health-red';
                return 'health-yellow';
            };
            const cards = [
                { title: 'PostgreSQL latency', value: (pg.latency_ms != null ? `${pg.latency_ms} ms` : 'n/a'), cls: (pg.reachable ? (pg.latency_ms > 250 ? 'health-yellow' : 'health-green') : 'health-red') },
                { title: 'Agents online/offline', value: `${agent.online_count ?? 0} / ${agent.offline_count ?? 0}`, cls: (agent.offline_count > 0 ? 'health-yellow' : 'health-green') },
                { title: 'Reprovision (нет токена)', value: `${agent.reprovision_required_count ?? 0}`, cls: ((agent.reprovision_required_count ?? 0) > 0 ? 'health-yellow' : 'health-green') },
                { title: 'Stale devices', value: `${agent.stale_count ?? 0}`, cls: ((agent.stale_count ?? 0) > 0 ? 'health-red' : 'health-green') },
                { title: 'WS UI подключений', value: `${svc.ui_ws_connections ?? 0}`, cls: 'health-green' },
                { title: 'Pending updates', value: `${upd.in_progress ?? 0}`, cls: ((upd.awaiting_handshake_confirm ?? 0) > 0 ? 'health-yellow' : 'health-green') },
                { title: 'Queued stuck', value: `${ops.queued_stuck ?? 0}`, cls: ((ops.queued_stuck ?? 0) > 0 ? 'health-red' : 'health-green') },
                { title: 'Operation watchdog', value: `${svc.operation_watchdog ?? 'unknown'}`, cls: toStatusClass(svc.operation_watchdog) },
            ];
            host.innerHTML = cards.map(c => `<div class="tech-card ${c.cls}"><h4>${c.title}</h4><div class="tech-value">${c.value}</div></div>`).join('');
        }

        function renderTechAlerts(alerts) {
            const host = document.getElementById('techAlertsList');
            if (!host) return;
            if (!alerts || alerts.length === 0) {
                host.innerHTML = '<div class="tech-alert-item severity-info"><strong>Нет активных алертов</strong><span>Система выглядит стабильно.</span></div>';
                return;
            }
            function renderAlertDetails(details) {
                if (!details || typeof details !== 'object') return '';
                if (Array.isArray(details.samples) && details.samples.length) {
                    return '<div class="tech-alert-details">' + details.samples.map((sample) => {
                        const parts = [];
                        if (sample.device_id) parts.push(`<code>${escapeHtml(sample.device_id)}</code>`);
                        if (sample.hostname) parts.push(escapeHtml(sample.hostname));
                        if (sample.ip_address) parts.push(escapeHtml(sample.ip_address));
                        if (sample.last_request_at) parts.push('last ' + escapeHtml(formatTechLifecycleTime(sample.last_request_at)));
                        return `<div>${parts.join(' · ')}</div>`;
                    }).join('') + '</div>';
                }
                const entries = Object.entries(details).filter(([key]) => key !== 'samples');
                if (!entries.length) return '';
                return '<div class="tech-alert-details">' + entries.map(([key, value]) => {
                    const rendered = typeof value === 'object' ? JSON.stringify(value) : String(value);
                    return `<div><strong>${escapeHtml(key)}:</strong> ${escapeHtml(rendered)}</div>`;
                }).join('') + '</div>';
            }
            host.innerHTML = alerts.map(a => {
                const link = a.link ? ` <a class="tech-alert-link" href="${escapeHtml(a.link)}" target="_blank" rel="noopener noreferrer">открыть</a>` : '';
                const severity = String(a.severity || 'info').toUpperCase();
                return `<div class="tech-alert-item severity-${(a.severity || 'info')}" data-tech-menu-item="1" data-tech-item-type="alert" data-tech-item-id="${escapeHtml(a.id || '')}" data-tech-related-log-id="${escapeHtml(a.related_log_id || '')}">
                    <strong>[${severity}] ${escapeHtml(a.summary || a.kind || '')}</strong>
                    <span>${a.detected_at ? escapeHtml(techFormatDate(a.detected_at)) + ' · ' : ''}${escapeHtml(a.kind || '')}${a.entity_id ? ` · ${escapeHtml(a.entity_id)}` : ''}${link}</span>
                    ${renderAlertDetails(a.details)}
                </div>`;
            }).join('');
        }

        function renderTechOverviewCards(overview) {
            const host = document.getElementById('techOverviewCards');
            if (!host) return;
            const pg = overview.postgres_health || {};
            const agent = overview.agent_health || {};
            const ops = overview.operations_health || {};
            const upd = overview.update_health || {};
            const svc = overview.service_health || {};
            const cards = [
                { title: 'PostgreSQL', value: pg.reachable ? `${pg.latency_ms ?? '—'} мс` : 'Недоступно', cls: (!pg.reachable ? 'health-red' : (Number(pg.latency_ms || 0) > 250 ? 'health-yellow' : 'health-green')) },
                { title: 'Агенты в сети', value: `${agent.online_count ?? 0} / ${agent.offline_count ?? 0}`, cls: ((agent.offline_count ?? 0) > 0 ? 'health-yellow' : 'health-green') },
                { title: 'Нужна перепривязка', value: `${agent.reprovision_required_count ?? 0}`, cls: ((agent.reprovision_required_count ?? 0) > 0 ? 'health-yellow' : 'health-green') },
                { title: 'Неактивные агенты', value: `${agent.stale_count ?? 0}`, cls: ((agent.stale_count ?? 0) > 0 ? 'health-red' : 'health-green') },
                { title: 'Подключения UI', value: `${svc.ui_ws_connections ?? 0}`, cls: 'health-green' },
                { title: 'Обновления', value: `${upd.in_progress ?? 0}`, cls: ((upd.awaiting_handshake_confirm ?? 0) > 0 ? 'health-yellow' : 'health-green') },
                { title: 'Застрявшие операции', value: `${(ops.queued_stuck ?? 0) + (ops.sent_stuck ?? 0) + (ops.in_progress_stuck ?? 0)}`, cls: (((ops.queued_stuck ?? 0) + (ops.sent_stuck ?? 0) + (ops.in_progress_stuck ?? 0)) > 0 ? 'health-red' : 'health-green') },
                { title: 'Watchdog операций', value: `${svc.operation_watchdog ?? 'unknown'}`, cls: (svc.operation_watchdog === 'ok' ? 'health-green' : 'health-red') },
            ];
            host.innerHTML = cards.map(c => `<div class="tech-card ${c.cls}"><h4>${escapeHtml(c.title)}</h4><div class="tech-value">${escapeHtml(String(c.value))}</div></div>`).join('');
        }

        function renderTechAlerts(alerts) {
            const host = document.getElementById('techAlertsList');
            if (!host) return;
            if (!alerts || alerts.length === 0) {
                host.innerHTML = '<div class="tech-alert-item severity-info"><strong>Активных алертов нет</strong><span>Система выглядит стабильно.</span></div>';
                return;
            }
            host.innerHTML = alerts.map(item => {
                const details = item.details && typeof item.details === 'object'
                    ? techRenderDetails(item.details)
                    : '';
                const samples = Array.isArray(item.details?.samples) && item.details.samples.length
                    ? '<div class="tech-alert-details">' + item.details.samples.map(sample => {
                        const parts = [];
                        if (sample.device_id) parts.push(`<code>${escapeHtml(sample.device_id)}</code>`);
                        if (sample.hostname) parts.push(escapeHtml(sample.hostname));
                        if (sample.ip_address) parts.push(escapeHtml(sample.ip_address));
                        if (sample.last_request_at) parts.push(`последний запрос ${escapeHtml(techFormatDate(sample.last_request_at))}`);
                        return `<div>${parts.join(' · ')}</div>`;
                    }).join('') + '</div>'
                    : '';
                const link = item.link ? ` <a href="${escapeHtml(item.link)}" target="_blank" rel="noopener noreferrer">открыть</a>` : '';
                return `<div class="tech-alert-item severity-${escapeHtml(item.severity || 'info')}">
                    <strong>${escapeHtml(item.summary || 'Без описания')}</strong>
                    <span>${escapeHtml(item.kind || '')}${item.entity_id ? ` · ${escapeHtml(item.entity_id)}` : ''}${link}</span>
                    ${details ? `<div class="tech-alert-details">${details}</div>` : ''}
                    ${samples}
                </div>`;
            }).join('');
        }

        function renderTechProblemLogs(logs) {
            const host = document.getElementById('techProblemLogsTable');
            if (!host) return;
            if (!logs || !logs.length) {
                host.innerHTML = '<div class="tech-table-wrap"><div class="tech-agent-detail"><div class="tech-empty-note">Пока нет warning/error логов в буфере.</div></div></div>';
                return;
            }
            host.innerHTML = `<div class="tech-table-wrap"><table class="tech-table">
                <thead><tr><th>Время</th><th>Уровень</th><th>Сообщение</th><th>Источник</th></tr></thead>
                <tbody>
                    ${logs.map(log => `<tr data-tech-menu-item="1" data-tech-item-type="log" data-tech-item-id="${escapeHtml(log.id || '')}">
                        <td>${escapeHtml(techFormatDate(log.timestamp))}</td>
                        <td><span class="tech-log-level ${escapeHtml(log.level_class || log.level || '')}">${escapeHtml(log.level_label || log.level || '—')}</span></td>
                        <td>${escapeHtml(log.message || '—')}</td>
                        <td>${escapeHtml([log.module, log.function, log.line ? `строка ${log.line}` : ''].filter(Boolean).join(' · ') || 'server')}</td>
                    </tr>`).join('')}
                </tbody>
            </table></div>`;
        }

        function renderTechAgentsTable(devices) {
            const body = document.getElementById('techAgentsTableBody');
            if (!body) return;
            if (!devices || !devices.length) {
                body.innerHTML = '<tr><td colspan="7" class="muted">Устройства не найдены.</td></tr>';
                return;
            }
            const sorted = devices.slice().sort((a, b) => {
                if (!!a.online !== !!b.online) return a.online ? -1 : 1;
                return new Date(b.last_seen_at || 0) - new Date(a.last_seen_at || 0);
            });
            body.innerHTML = sorted.map(device => {
                const stale = techIsStale(device.last_seen_at);
                const selected = techSelectedDeviceId === device.device_id ? 'tech-row-selected' : '';
                const problems = [];
                if (stale) problems.push('неактивен');
                if (device.provisioning_summary?.reprovision_required) problems.push('перепривязка');
                if (techUpdateKind(device.update_summary) === 'bad') problems.push('ошибка обновления');
                return `<tr class="tech-row-clickable ${selected}" data-tech-device-id="${escapeHtml(device.device_id)}">
                    <td>
                        <span class="tech-device-title">${escapeHtml(device.hostname || device.device_id)}</span>
                        <div class="tech-device-meta"><code>${escapeHtml(device.device_id)}</code></div>
                        <div class="tech-device-meta">${escapeHtml(device.agent_version || 'версия неизвестна')} · ${escapeHtml(device.os || 'ОС неизвестна')}</div>
                    </td>
                    <td>${techPill(device.online ? 'В сети' : 'Офлайн', device.online ? (stale ? 'warn' : 'ok') : 'bad')}</td>
                    <td><div>${escapeHtml(techFormatDate(device.last_seen_at))}</div><div class="tech-device-meta">${escapeHtml(techFormatRelative(device.last_seen_at))}</div></td>
                    <td><div>${escapeHtml(techFormatRelative(device.last_handshake_at))}</div><div class="tech-device-meta">${escapeHtml(techFormatDate(device.last_handshake_at))}</div></td>
                    <td>${techPill(techProvisioningLabel(device.provisioning_summary), techProvisioningKind(device.provisioning_summary))}</td>
                    <td>${techPill(techUpdateLabel(device.update_summary), techUpdateKind(device.update_summary))}</td>
                    <td>${problems.length ? escapeHtml(problems.join(', ')) : '<span class="muted">нет</span>'}</td>
                </tr>`;
            }).join('');
        }

        function renderTechAuditTable(hostId, rows, mode) {
            const host = document.getElementById(hostId);
            if (!host) return;
            if (!rows || !rows.length) {
                host.innerHTML = '<div class="tech-table-wrap"><div class="tech-agent-detail"><div class="tech-empty-note">Записей пока нет.</div></div></div>';
                return;
            }
            const headers = mode === 'agent'
                ? '<tr><th>Время</th><th>Устройство</th><th>Событие</th><th>Уровень</th><th>Контекст</th></tr>'
                : '<tr><th>Время</th><th>Пользователь</th><th>Событие</th><th>Кто выполнил</th><th>Контекст</th></tr>';
            host.innerHTML = `<div class="tech-table-wrap"><table class="tech-table">
                <thead>${headers}</thead>
                <tbody>
                    ${rows.map(row => mode === 'agent'
                        ? `<tr>
                            <td>${escapeHtml(techFormatDate(row.created_at))}</td>
                            <td><code>${escapeHtml(row.device_id || '—')}</code></td>
                            <td>${escapeHtml(row.event_label || row.event_type || '—')}</td>
                            <td>${techPill(row.severity_label || row.severity || '—', row.severity === 'error' || row.severity === 'critical' ? 'bad' : (row.severity === 'warning' ? 'warn' : 'ok'))}</td>
                            <td><div class="tech-json-preview">${techRenderDetails(row.details_json)}</div></td>
                        </tr>`
                        : `<tr>
                            <td>${escapeHtml(techFormatDate(row.created_at))}</td>
                            <td>${escapeHtml(row.user_login || '—')}</td>
                            <td>${escapeHtml(row.action_label || row.action || '—')}</td>
                            <td>${escapeHtml(row.actor_id || '—')}</td>
                            <td><div class="tech-json-preview">${techRenderDetails(row.details_json)}</div></td>
                        </tr>`
                    ).join('')}
                </tbody>
            </table></div>`;
        }

        function renderTechStuckOpsTable(rows) {
            const host = document.getElementById('techStuckOpsTable');
            if (!host) return;
            if (!rows || !rows.length) {
                host.innerHTML = '<div class="tech-table-wrap"><div class="tech-agent-detail"><div class="tech-empty-note">Застрявших операций нет.</div></div></div>';
                return;
            }
            host.innerHTML = `<div class="tech-table-wrap"><table class="tech-table">
                <thead><tr><th>Операция</th><th>Устройство</th><th>Тип</th><th>Статус</th><th>Когда стартовала</th><th>Дедлайн</th></tr></thead>
                <tbody>
                    ${rows.map(row => `<tr>
                        <td><code>${escapeHtml((row.operation_id || '').slice(0, 8))}</code></td>
                        <td><code>${escapeHtml(row.device_id || '—')}</code></td>
                        <td>${escapeHtml(row.kind || '—')}</td>
                        <td>${escapeHtml(row.status || '—')}</td>
                        <td>${escapeHtml(techFormatDate(row.started_at || row.sent_at || row.queued_at))}</td>
                        <td>${escapeHtml(techFormatDate(row.deadline_at))}</td>
                    </tr>`).join('')}
                </tbody>
            </table></div>`;
        }

        function selectTechAgent(deviceId) {
            if (!deviceId) return;
            techSelectedDeviceId = deviceId;
            renderTechAgentsTable(techDevicesCache);
            loadTechAgentDetail(deviceId);
        }

        async function loadTechAgentDetail(deviceId) {
            const shell = document.getElementById('techAgentDetailShell');
            if (!shell || !deviceId) return;
            shell.innerHTML = '<div class="tech-agent-detail"><div class="loading">Загрузка карточки агента...</div></div>';
            try {
                const headers = getAuthHeaders();
                const [deviceRes, timelineRes, toolsetRes, debugRes, desiredRes, logsRes] = await Promise.all([
                    fetch(`/api/devices/${encodeURIComponent(deviceId)}`, { headers }),
                    fetch(`/api/admin/tech/agents/${encodeURIComponent(deviceId)}/timeline`, { headers }),
                    fetch(`/api/devices/${encodeURIComponent(deviceId)}/toolset`, { headers }),
                    fetch(`/api/devices/${encodeURIComponent(deviceId)}/modules/debug`, { headers }),
                    fetch(`/api/devices/${encodeURIComponent(deviceId)}/modules/desired_diff`, { headers }),
                    fetch(`/api/admin/tech/logs?limit=20&contains=${encodeURIComponent(deviceId)}`, { headers }),
                ]);
                const deviceData = await responseToJson(deviceRes);
                const timelineData = await responseToJson(timelineRes);
                const toolsetData = await responseToJson(toolsetRes);
                const debugData = await responseToJson(debugRes);
                const desiredData = await responseToJson(desiredRes);
                const logsData = await responseToJson(logsRes);
                renderTechAgentDetail(
                    deviceData.device || {},
                    timelineData,
                    toolsetData.status === 'ok' ? toolsetData : null,
                    debugData.status === 'ok' ? debugData : null,
                    desiredData.status === 'ok' ? desiredData : null,
                    logsData.logs || timelineData.problem_logs || []
                );
            } catch (e) {
                shell.innerHTML = `<div class="tech-agent-detail"><div class="error-message">Не удалось загрузить карточку агента: ${escapeHtml(e.message || String(e))}</div></div>`;
            }
        }

        function techRenderTimelineList(title, rows) {
            if (!rows || !rows.length) {
                return `<div class="tech-mini-panel"><h4>${escapeHtml(title)}</h4><div class="tech-empty-note">Событий пока нет.</div></div>`;
            }
            return `<div class="tech-mini-panel">
                <h4>${escapeHtml(title)}</h4>
                <div class="tech-timeline" role="list">
                    ${rows.slice(0, 8).map(row => `<div class="tech-timeline-item" role="listitem">
                        <div class="tl-time">${escapeHtml(techFormatDate(row.created_at || row.at))}</div>
                        <div class="tl-title">${escapeHtml(row.event_label || row.event_type || 'Событие')}</div>
                        <div class="tl-actor">${escapeHtml(row.severity_label || row.severity || '')}${row.source ? ' · ' + escapeHtml(row.source) : ''}</div>
                    </div>`).join('')}
                </div>
            </div>`;
        }

        function renderTechAgentDetail(device, timelineData, toolsetData, debugData, desiredData, logs) {
            const shell = document.getElementById('techAgentDetailShell');
            if (!shell) return;
            const current = timelineData.current_state || {};
            techSelectedModules = (debugData?.device_modules || []).slice();
            const outboxCounts = timelineData.outbox_summary?.counts || {};
            const issueSummary = timelineData.issue_summary || [];
            const toolsByModule = toolsetData?.tools_by_module || {};
            const desiredDiff = desiredData?.diff || [];
            const mismatches = debugData?.mismatches || [];
            const recentOps = timelineData.recent_operations || debugData?.recent_operations || [];
            const authTimeline = timelineData.auth_timeline || [];
            const handshakeTimeline = timelineData.handshake_timeline || [];
            const updateTimeline = timelineData.update_timeline || [];
            const actionText = techAgentActionState.deviceId === device.device_id && techAgentActionState.text
                ? techAgentActionState.text
                : 'Нажмите одну из кнопок выше, чтобы получить живой ответ от агента.';

            shell.innerHTML = `
                <div class="tech-agent-detail">
                    <div class="tech-agent-head">
                        <div>
                            <h3>${escapeHtml(device.hostname || device.device_id || 'Агент')}</h3>
                            <div class="tech-agent-subtitle">
                                <code>${escapeHtml(device.device_id || '—')}</code> · ${escapeHtml(device.agent_version || 'версия неизвестна')} · ${escapeHtml(device.os || 'ОС неизвестна')}
                            </div>
                        </div>
                        <div class="tech-inline-list">
                            ${techPill(current.online ? 'В сети' : 'Офлайн', current.online ? (current.stale ? 'warn' : 'ok') : 'bad')}
                            ${techPill(techProvisioningLabel(device.provisioning_summary), techProvisioningKind(device.provisioning_summary))}
                            ${techPill(techUpdateLabel(device.update_summary), techUpdateKind(device.update_summary))}
                        </div>
                    </div>

                    <div class="tech-actions-bar">
                        <button type="button" class="btn btn-secondary btn-sm" data-tech-action="get_status">Статус</button>
                        <button type="button" class="btn btn-secondary btn-sm" data-tech-action="get_history">История</button>
                        <button type="button" class="btn btn-secondary btn-sm" data-tech-action="list_tasks">Задачи</button>
                        <button type="button" class="btn btn-secondary btn-sm" data-tech-action="refresh_toolset">Обновить toolset</button>
                        <button type="button" class="btn btn-secondary btn-sm" data-tech-action="sync_modules">Синхронизировать модули</button>
                        <button type="button" class="btn btn-secondary btn-sm" data-tech-action="reconcile">Сверить состояние</button>
                    </div>

                    <div class="tech-kpi-grid">
                        <div class="tech-kpi-card"><label>Последний контакт</label><value>${escapeHtml(techFormatDate(device.last_seen_at))}</value></div>
                        <div class="tech-kpi-card"><label>Возраст handshake</label><value>${escapeHtml(current.last_handshake_age_sec != null ? `${Math.floor(current.last_handshake_age_sec / 60)} мин` : '—')}</value></div>
                        <div class="tech-kpi-card"><label>Хеш toolset</label><value>${escapeHtml(toolsetData?.toolset_hash || device.toolset_hash || '—')}</value></div>
                        <div class="tech-kpi-card"><label>Инструментов</label><value>${escapeHtml(String(toolsetData?.tool_count ?? device.tools_count ?? 0))}</value></div>
                        <div class="tech-kpi-card"><label>Ожидают подтверждения</label><value>${escapeHtml(String(current.pending_consents_count ?? 0))}</value></div>
                        <div class="tech-kpi-card"><label>Очередь outbox</label><value>${escapeHtml(String((outboxCounts.pending || 0) + (outboxCounts.sent || 0)))}</value></div>
                    </div>

                    ${issueSummary.length ? `<div class="tech-mini-panel"><h4>Что требует внимания сейчас</h4><ul class="tech-issue-list">${issueSummary.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul></div>` : ''}

                    <div class="tech-mini-grid">
                        ${techRenderTimelineList('Лента авторизации', authTimeline)}
                        ${techRenderTimelineList('Лента handshake', handshakeTimeline)}
                        ${techRenderTimelineList('Лента обновления', updateTimeline)}
                    </div>

                    <div class="tech-mini-panel">
                        <h4>Модульная диагностика</h4>
                        ${desiredDiff.length ? `<div class="tech-inline-list" style="margin-bottom: 10px;">
                            ${desiredData.summary ? techPill(`OK: ${desiredData.summary.ok || 0}`, 'ok') : ''}
                            ${desiredData.summary?.missing ? techPill(`Отсутствуют: ${desiredData.summary.missing}`, 'bad') : ''}
                            ${desiredData.summary?.version_mismatch ? techPill(`Версия не совпадает: ${desiredData.summary.version_mismatch}`, 'warn') : ''}
                            ${desiredData.summary?.not_removed ? techPill(`Не удалены: ${desiredData.summary.not_removed}`, 'warn') : ''}
                        </div>` : '<div class="tech-empty-note" style="margin-bottom:10px;">Желаемое состояние модулей не заполнено.</div>'}
                        <div class="tech-table-wrap">
                            <table class="tech-table">
                                <thead><tr><th>Модуль</th><th>Desired</th><th>Actual</th><th>Drift</th><th>Действие</th></tr></thead>
                                <tbody>
                                    ${(debugData?.device_modules || []).map(mod => {
                                        const diff = desiredDiff.find(item => item.module_name === mod.module_name);
                                        const tools = toolsByModule[mod.module_name] || [];
                                        const driftLabel = diff?.diff_status || (tools.length ? 'ok' : 'no_tools');
                                        const driftKind = driftLabel === 'ok' ? 'ok' : (driftLabel === 'missing' ? 'bad' : 'warn');
                                        return `<tr>
                                            <td><strong>${escapeHtml(mod.module_name)}</strong><br><span class="tech-device-meta">${escapeHtml(mod.version || '—')}</span></td>
                                            <td>${escapeHtml(diff ? `${diff.desired_state || '—'} ${diff.desired_version || ''}`.trim() : '—')}</td>
                                            <td>${escapeHtml(`${mod.state || '—'} · tools: ${tools.length}`)}</td>
                                            <td>${techPill(driftLabel, driftKind)}</td>
                                            <td><button type="button" class="btn btn-secondary btn-sm" data-tech-action="verify_module" data-module-name="${escapeHtml(mod.module_name)}" data-module-version="${escapeHtml(mod.version || '')}">Проверить</button></td>
                                        </tr>`;
                                    }).join('') || '<tr><td colspan="5" class="muted">Модулей нет.</td></tr>'}
                                </tbody>
                            </table>
                        </div>
                        ${mismatches.length ? `<div class="tech-json-preview" style="margin-top:10px;">${escapeHtml(JSON.stringify(mismatches, null, 2))}</div>` : ''}
                    </div>

                    <div class="tech-mini-grid">
                        <div class="tech-mini-panel">
                            <h4>Последние операции</h4>
                            ${recentOps.length ? `<div class="tech-table-wrap"><table class="tech-table">
                                <thead><tr><th>Операция</th><th>Тип</th><th>Статус</th><th>Ошибка</th></tr></thead>
                                <tbody>${recentOps.slice(0, 8).map(op => `<tr>
                                    <td><code>${escapeHtml((op.operation_id || '').slice(0, 8))}</code></td>
                                    <td>${escapeHtml(op.kind || '—')}</td>
                                    <td>${escapeHtml(op.status_label || op.status || '—')}</td>
                                    <td>${escapeHtml(op.error_code || op.error_message || '—')}</td>
                                </tr>`).join('')}</tbody>
                            </table></div>` : '<div class="tech-empty-note">Операций пока нет.</div>'}
                        </div>
                        <div class="tech-mini-panel">
                            <h4>Состояние outbox</h4>
                            <div class="tech-inline-list" style="margin-bottom: 10px;">
                                ${techPill(`Ожидают: ${outboxCounts.pending || 0}`, (outboxCounts.pending || 0) ? 'warn' : 'ok')}
                                ${techPill(`Отправлены: ${outboxCounts.sent || 0}`, (outboxCounts.sent || 0) ? 'warn' : 'ok')}
                                ${techPill(`Ошибки: ${outboxCounts.failed || 0}`, (outboxCounts.failed || 0) ? 'bad' : 'ok')}
                            </div>
                            ${timelineData.outbox_summary?.recent?.length ? `<div class="tech-table-wrap"><table class="tech-table">
                                <thead><tr><th>Команда</th><th>Статус</th><th>Время</th></tr></thead>
                                <tbody>${timelineData.outbox_summary.recent.slice(0, 8).map(row => `<tr>
                                    <td>${escapeHtml(row.command || '—')}</td>
                                    <td>${escapeHtml(row.status_label || row.status || '—')}</td>
                                    <td>${escapeHtml(techFormatDate(row.created_at))}</td>
                                </tr>`).join('')}</tbody>
                            </table></div>` : '<div class="tech-empty-note">Записей outbox нет.</div>'}
                        </div>
                    </div>

                    <div class="tech-mini-grid">
                        <div class="tech-mini-panel">
                            <h4>Последние ошибки и предупреждения</h4>
                            ${timelineData.last_errors?.length ? `<div class="tech-timeline">${timelineData.last_errors.map(row => `<div class="tech-timeline-item">
                                <div class="tl-time">${escapeHtml(techFormatDate(row.created_at))}</div>
                                <div class="tl-title">${escapeHtml(row.event_label || row.event_type || 'Событие')}</div>
                                <div class="tl-actor">${escapeHtml(row.severity_label || row.severity || '')}</div>
                            </div>`).join('')}</div>` : '<div class="tech-empty-note">Критичных событий не найдено.</div>'}
                        </div>
                        <div class="tech-mini-panel">
                            <h4>Проблемные логи по агенту</h4>
                            ${logs.length ? `<div class="tech-table-wrap"><table class="tech-table">
                                <thead><tr><th>Время</th><th>Уровень</th><th>Сообщение</th></tr></thead>
                                <tbody>${logs.slice(0, 8).map(log => `<tr>
                                    <td>${escapeHtml(techFormatDate(log.timestamp))}</td>
                                    <td>${escapeHtml(log.level_label || log.level || '—')}</td>
                                    <td>${escapeHtml(log.message || '—')}</td>
                                </tr>`).join('')}</tbody>
                            </table></div>` : '<div class="tech-empty-note">Логи по этому агенту в буфере не найдены.</div>'}
                        </div>
                    </div>

                    <div class="tech-mini-panel">
                        <h4>Результат последней диагностической команды</h4>
                        <pre id="techAgentActionResult" class="tech-result-box">${escapeHtml(actionText)}</pre>
                    </div>
                </div>`;
        }

        async function handleTechActionButton(button) {
            const action = button.getAttribute('data-tech-action');
            const deviceId = techSelectedDeviceId;
            if (!action || !deviceId) return;
            if (action === 'sync_modules') {
                await runTechModuleAction(deviceId, 'sync_modules');
                return;
            }
            if (action === 'reconcile') {
                await runTechModuleAction(deviceId, 'reconcile');
                return;
            }
            if (action === 'verify_module') {
                await runTechModuleAction(deviceId, 'verify_module', {
                    module_name: button.getAttribute('data-module-name'),
                    version: button.getAttribute('data-module-version'),
                });
                return;
            }
            await runTechAgentAction(deviceId, action);
        }

        async function runTechAgentAction(deviceId, action) {
            techSetActionState(deviceId, `Выполняю команду «${techActionLabel(action)}»...`);
            try {
                const response = await fetch(`/api/admin/tech/agents/${encodeURIComponent(deviceId)}/actions`, {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({ action, limit: 20 }),
                });
                const data = await responseToJson(response);
                if (!response.ok || data.status !== 'ok') {
                    throw new Error(techHumanizeActionError(action, data.error || ''));
                }
                const payload = data.result == null
                    ? `Команда «${techActionLabel(action)}» выполнена успешно.`
                    : `Команда «${techActionLabel(action)}» выполнена успешно.\n\n${JSON.stringify(data.result, null, 2)}`;
                techSetActionState(deviceId, payload);
                setTimeout(() => loadTechAgentDetail(deviceId), 1500);
            } catch (e) {
                techSetActionState(deviceId, 'Ошибка: ' + techHumanizeActionError(action, e.message || e));
            }
        }

        async function runTechModuleAction(deviceId, action, payload) {
            techSetActionState(deviceId, `Выполняю команду «${techActionLabel(action)}»...`);
            try {
                let url = '';
                let body = {};
                if (action === 'sync_modules') {
                    url = `/api/devices/${encodeURIComponent(deviceId)}/modules/sync`;
                } else if (action === 'reconcile') {
                    url = `/api/devices/${encodeURIComponent(deviceId)}/modules/reconcile`;
                } else if (action === 'verify_module') {
                    url = `/api/devices/${encodeURIComponent(deviceId)}/modules/verify`;
                    body = payload || {};
                } else {
                    throw new Error('Неизвестное модульное действие');
                }
                const response = await fetch(url, {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify(body),
                });
                const data = await responseToJson(response);
                if (!response.ok || (data.status !== 'ok' && data.status !== 'accepted')) {
                    throw new Error(data.error || 'Команда завершилась с ошибкой');
                }
                techSetActionState(
                    deviceId,
                    `Команда «${techActionLabel(action)}» отправлена.\n\n${JSON.stringify(data, null, 2)}`
                );
                setTimeout(() => loadTechAgentDetail(deviceId), 1500);
            } catch (e) {
                techSetActionState(deviceId, `Ошибка: ${e.message || e}`);
            }
        }

        function formatTechLifecycleTime(iso) {
            if (!iso) return '—';
            try { return new Date(iso).toLocaleString('ru-RU'); } catch (e) { return iso; }
        }

        function renderTechLifecycleVisual(data) {
            const shell = document.getElementById('techLifecycleVisual');
            if (!shell) return;
            if (!data || data.status !== 'ok') {
                shell.style.display = 'none';
                shell.innerHTML = '';
                return;
            }
            shell.style.display = 'block';
            const t = data.ticket || {};
            const esc = (v) => escapeHtml(String(v == null ? '' : v));
            const rail = data.milestone_rail || [];
            const slaLane = data.sla_lane || [];
            const timeline = data.timeline || [];
            const ops = data.related_operations || [];

            const head = `
                <div class="tech-lifecycle-ticket-head">
                    <h3>${esc(t.title || 'Тикет')}</h3>
                    <div class="tech-lifecycle-meta">
                        <span><strong>Код:</strong> ${esc(t.ticket_code)}</span>
                        <span><strong>ID:</strong> <code>${esc(t.ticket_id)}</code></span>
                        ${t.device_id ? `<span><strong>Устройство:</strong> <code>${esc(t.device_id)}</code></span>` : ''}
                        ${t.assignee_id ? `<span><strong>Исполнитель:</strong> ${esc(t.assignee_id)}</span>` : '<span><strong>Исполнитель:</strong> —</span>'}
                        ${t.queue_id != null ? `<span><strong>Очередь:</strong> ${esc(t.queue_id)}</span>` : ''}
                        <span class="status-pill">${esc(t.status || '')}</span>
                    </div>
                </div>`;

            const milestonesHtml = '<div class="tech-milestones-rail" role="list">' + rail.map(m => {
                const cls = m.reached ? 'tech-ms-reached' : 'tech-ms-pending';
                const tip = m.at ? esc(formatTechLifecycleTime(m.at)) : 'Ещё не зафиксировано';
                return `<div class="tech-milestone-chip ${cls}" role="listitem" title="${tip}">
                    <span class="tech-ms-icon">${m.icon || ''}</span>
                    <span class="tech-ms-label">${esc(m.label)}</span>
                    ${m.at ? `<span class="tech-ms-time">${esc(formatTechLifecycleTime(m.at))}</span>` : '<span class="tech-ms-time">—</span>'}
                </div>`;
            }).join('') + '</div>';

            const slaHtml = slaLane.length
                ? `<div class="tech-sla-lane" role="region" aria-label="SLA">${slaLane.map(s => `<span class="tech-sla-item">${s.icon || ''} <strong>${esc(s.label)}</strong> ${esc(formatTechLifecycleTime(s.at))}</span>`).join('')}</div>`
                : '';

            function linkRender(link) {
                if (!link || !link.href) return '';
                const dm = (link.href || '').match(/#device-(.+)$/);
                if (link.rel === 'device' && dm) {
                    return `<a href="#" class="tech-lifecycle-jump" data-jump="device" data-device-id="${esc(dm[1])}">${esc(link.label)}</a>`;
                }
                return `<a href="${esc(link.href)}" target="_blank" rel="noopener noreferrer">${esc(link.label)}</a>`;
            }

            const sortedMilestones = rail.filter(m => m.at).slice().sort((a, b) => new Date(a.at) - new Date(b.at));
            let lastPhaseKey = null;
            const feed = [];
            timeline.forEach(e => feed.push({ sortAt: e.at, type: 'event', payload: e }));
            slaLane.forEach(s => feed.push({ sortAt: s.at, type: 'sla', payload: s }));
            feed.sort((a, b) => new Date(a.sortAt) - new Date(b.sortAt));

            let timelineHtml = '<div class="tech-timeline" role="list">';
            for (const item of feed) {
                let phaseKey = '_start';
                let phaseLabel = 'События';
                const tms = new Date(item.sortAt).getTime();
                for (const m of sortedMilestones) {
                    if (new Date(m.at).getTime() <= tms) {
                        phaseKey = m.key;
                        phaseLabel = `${m.icon || ''} ${m.label}`.trim();
                    }
                }
                if (sortedMilestones.length && phaseKey !== lastPhaseKey) {
                    timelineHtml += `<div class="tech-timeline-phase">${esc(phaseLabel)}</div>`;
                    lastPhaseKey = phaseKey;
                }

                if (item.type === 'sla') {
                    const s = item.payload;
                    timelineHtml += `<div class="tech-timeline-item tech-tl-sla" role="listitem">
                        <div class="tl-time">${esc(formatTechLifecycleTime(s.at))}</div>
                        <div class="tl-title">${s.icon || ''} ${esc(s.label)}</div>
                    </div>`;
                } else {
                    const e = item.payload;
                    const links = (e.links || []).map(linkRender).filter(Boolean).join(' · ');
                    timelineHtml += `<div class="tech-timeline-item" role="listitem">
                        <div class="tl-time">${esc(formatTechLifecycleTime(e.at))}</div>
                        <div class="tl-title">${e.icon || ''} ${esc(e.title || e.kind || '')}</div>
                        <div class="tl-actor">Актор: ${esc(e.actor_label || '')}</div>
                        ${e.status_after ? `<div class="tl-actor">Статус → ${esc(e.status_after)}</div>` : ''}
                        ${e.operation_id ? `<div class="tl-actor">Операция: <code>${esc(e.operation_id)}</code></div>` : ''}
                        ${links ? `<div class="tl-links">${links}</div>` : ''}
                    </div>`;
                }
            }
            timelineHtml += '</div>';

            const opsHtml = ops.length ? `<div class="tech-related-ops"><h4>Связанные операции</h4><div class="tech-ops-grid">` +
                ops.map(op => {
                    const lns = (op.links || []).map(linkRender).filter(Boolean).join(' · ');
                    return `<div class="tech-op-card">
                        <div class="op-kind">${op.icon || ''} ${esc(op.kind)} · <code>${esc(op.operation_id)}</code></div>
                        <div>${esc(op.status)} · ${esc(formatTechLifecycleTime(op.queued_at))}</div>
                        ${lns ? `<div class="tl-links" style="margin-top:6px;">${lns}</div>` : ''}
                    </div>`;
                }).join('') + '</div></div>' : '';

            shell.innerHTML = head + milestonesHtml + slaHtml + timelineHtml + opsHtml;
        }

        async function loadTechLifecycle() {
            const ticketId = (document.getElementById('techTicketIdInput')?.value || '').trim();
            const output = document.getElementById('techLifecycleJson');
            const shell = document.getElementById('techLifecycleVisual');
            if (!output && !shell) return;
            if (!ticketId) {
                if (output) output.textContent = 'Укажите ticket_id';
                if (shell) { shell.style.display = 'none'; shell.innerHTML = ''; }
                return;
            }
            try {
                const r = await fetch('/api/admin/tech/tickets/' + encodeURIComponent(ticketId) + '/lifecycle', {
                    headers: getAuthHeaders(),
                });
                const data = await r.json();
                if (output) output.textContent = JSON.stringify(data, null, 2);
                renderTechLifecycleVisual(data);
                if (r.ok) {
                    const d = document.getElementById('techLifecycleRawDetails');
                    if (d) d.open = false;
                }
            } catch (e) {
                const msg = 'Ошибка загрузки lifecycle: ' + (e.message || e);
                if (output) output.textContent = msg;
                renderTechLifecycleVisual(null);
            }
        }

        // ============================================
        // Users Tab Functions
        // ============================================

        async function loadUsersTab() {
            const loadingEl = document.getElementById('usersListLoading');
            const errorEl = document.getElementById('usersListError');
            const containerEl = document.getElementById('usersListContainer');
            const emptyEl = document.getElementById('usersListEmpty');
            const tbodyEl = document.getElementById('usersListTableBody');
            if (!loadingEl || !tbodyEl) return;
            loadingEl.style.display = 'block';
            if (errorEl) errorEl.style.display = 'none';
            if (emptyEl) emptyEl.style.display = 'none';
            if (containerEl) containerEl.style.display = 'none';
            try {
                const r = await fetch('/api/admin/users?include_inactive=true', { headers: getAuthHeaders() });
                const data = await r.json();
                loadingEl.style.display = 'none';
                if (!r.ok) {
                    if (errorEl) { errorEl.textContent = data.error || 'API недоступен'; errorEl.style.display = 'block'; }
                    return;
                }
                const users = data.users || [];
                if (users.length === 0) {
                    if (emptyEl) emptyEl.style.display = 'block';
                    return;
                }
                if (containerEl) containerEl.style.display = 'block';
                const roles = ['admin', 'support', 'auditor', 'user'];
                tbodyEl.innerHTML = users.map(u => {
                    const lastLogin = u.last_login_at ? new Date(u.last_login_at).toLocaleString('ru-RU') : '—';
                    const roleOpts = roles.map(r => `<option value="${r}"${(u.actor_role || '') === r ? ' selected' : ''}>${r}</option>`).join('');
                    return `<tr data-login="${(u.user_login || '').replace(/"/g, '&quot;')}">
                        <td><strong>${(u.user_login || '').replace(/</g, '&lt;')}</strong></td>
                        <td><select class="users-role-select" data-login="${(u.user_login || '').replace(/"/g, '&quot;')}" title="Изменить роль">${roleOpts}</select></td>
                        <td>${u.is_active !== false ? 'Да' : 'Нет'}</td>
                        <td>${lastLogin}</td>
                        <td>
                            <button type="button" class="btn btn-sm btn-secondary users-pwd-btn" data-login="${(u.user_login || '').replace(/"/g, '&quot;')}">Сменить пароль</button>
                            ${u.is_active !== false ? `<button type="button" class="btn btn-sm users-deactivate-btn" data-login="${(u.user_login || '').replace(/"/g, '&quot;')}">Деактивировать</button>` : ''}
                        </td>
                    </tr>`;
                }).join('');
                bindUsersTabHandlers();
            } catch (e) {
                loadingEl.style.display = 'none';
                if (errorEl) { errorEl.textContent = 'Ошибка: ' + e.message; errorEl.style.display = 'block'; }
            }
        }

        function bindUsersTabHandlers() {
            document.querySelectorAll('.users-role-select').forEach(sel => {
                sel.onchange = function() {
                    const login = this.getAttribute('data-login');
                    const role = this.value;
                    if (!login) return;
                    fetch('/api/admin/users/' + encodeURIComponent(login), {
                        method: 'PATCH',
                        headers: getAuthHeaders(true),
                        body: JSON.stringify({ actor_role: role })
                    }).then(r => r.json()).then(data => {
                        if (data.status === 'ok') {
                            if (typeof queueCachedUsers !== 'undefined') queueCachedUsers = [];
                            if (typeof queueRenderTable === 'function') queueRenderTable();
                        } else alert(data.error || 'Ошибка');
                    }).catch(e => alert(e.message));
                };
            });
            document.querySelectorAll('.users-pwd-btn').forEach(btn => {
                btn.onclick = function() {
                    const login = this.getAttribute('data-login');
                    if (!login) return;
                    const pwd = prompt('Новый пароль для ' + login + ':');
                    if (pwd == null || pwd === '') return;
                    fetch('/api/admin/users/' + encodeURIComponent(login) + '/password', {
                        method: 'POST',
                        headers: getAuthHeaders(true),
                        body: JSON.stringify({ password: pwd })
                    }).then(r => r.json()).then(data => {
                        if (data.status === 'ok') alert('Пароль обновлён');
                        else alert(data.error || 'Ошибка');
                    }).catch(e => alert(e.message));
                };
            });
            document.querySelectorAll('.users-deactivate-btn').forEach(btn => {
                btn.onclick = function() {
                    const login = this.getAttribute('data-login');
                    if (!login) return;
                    if (!confirm('Деактивировать пользователя ' + login + '? Он не сможет входить в панель.')) return;
                    fetch('/api/admin/users/' + encodeURIComponent(login) + '/deactivate', {
                        method: 'POST',
                        headers: getAuthHeaders(true),
                        body: JSON.stringify({})
                    }).then(r => r.json()).then(data => {
                        if (data.status === 'ok') loadUsersTab();
                        else alert(data.error || 'Ошибка');
                    }).catch(e => alert(e.message));
                };
            });
        }

        (function initUsersForm() {
            const form = document.getElementById('usersAddForm');
            if (!form) return;
            form.onsubmit = async function(e) {
                e.preventDefault();
                const loginEl = document.getElementById('usersAddLogin');
                const pwdEl = document.getElementById('usersAddPassword');
                const roleEl = document.getElementById('usersAddRole');
                const errEl = document.getElementById('usersAddError');
                const okEl = document.getElementById('usersAddSuccess');
                if (errEl) errEl.style.display = 'none';
                if (okEl) okEl.style.display = 'none';
                const login = (loginEl && loginEl.value || '').trim();
                const password = pwdEl && pwdEl.value;
                const role = roleEl && roleEl.value || 'support';
                if (!login) { if (errEl) { errEl.textContent = 'Введите логин'; errEl.style.display = 'block'; } return; }
                if (!password) { if (errEl) { errEl.textContent = 'Введите пароль'; errEl.style.display = 'block'; } return; }
                try {
                    const r = await fetch('/api/admin/users', {
                        method: 'POST',
                        headers: getAuthHeaders(true),
                        body: JSON.stringify({ login: login, password: password, actor_role: role })
                    });
                    const data = await r.json();
                    if (data.status === 'ok') {
                        if (okEl) { okEl.textContent = 'Пользователь ' + login + ' создан'; okEl.style.display = 'block'; setTimeout(() => { okEl.style.display = 'none'; }, 3000); }
                        if (pwdEl) pwdEl.value = '';
                        if (typeof queueCachedUsers !== 'undefined') queueCachedUsers = [];
                        if (typeof queueRenderTable === 'function') queueRenderTable();
                        loadUsersTab();
                    } else {
                        if (errEl) { errEl.textContent = data.error || 'Ошибка'; errEl.style.display = 'block'; }
                    }
                } catch (e) {
                    if (errEl) { errEl.textContent = e.message; errEl.style.display = 'block'; }
                }
            };
        })();

        // ============================================
        // Agent Updates Tab
        // ============================================

        let agentUpdatesTabInitialized = false;

        async function loadAgentUpdatesTab() {
            const deviceSelect = document.getElementById('agentUpdatesDeviceSelect');
            const buildSelect = document.getElementById('agentUpdatesBuildSelect');
            const refreshBuildsBtn = document.getElementById('agentUpdatesRefreshBuilds');
            const triggerBtn = document.getElementById('agentUpdatesTriggerBtn');
            if (!deviceSelect || !buildSelect) return;

            if (!agentUpdatesTabInitialized) {
                agentUpdatesTabInitialized = true;
                if (refreshBuildsBtn) refreshBuildsBtn.addEventListener('click', () => loadAgentUpdatesBuilds(true));
                if (triggerBtn) triggerBtn.addEventListener('click', triggerAgentUpdate);
                const uploadForm = document.getElementById('agentBuildUploadForm');
                if (uploadForm) uploadForm.addEventListener('submit', submitAgentBuildUpload);
                const uploadFile = document.getElementById('agentBuildUploadFile');
                if (uploadFile) uploadFile.addEventListener('change', syncAgentBuildUploadArchiveType);
                const bulkAllEl = document.getElementById('agentUpdatesBulkAllOnline');
                const bulkDevicesWrap = document.getElementById('agentUpdatesBulkDevicesWrap');
                if (bulkAllEl && bulkDevicesWrap) bulkAllEl.addEventListener('change', function() { bulkDevicesWrap.style.display = this.checked ? 'none' : 'block'; });
                const bulkBtn = document.getElementById('agentUpdatesBulkBtn');
                if (bulkBtn) bulkBtn.addEventListener('click', triggerBulkAgentUpdate);
            }

            // Устройства — из /api/agents (только онлайн)
            try {
                const r = await fetch('/api/agents', { headers: getAuthHeaders() });
                const data = await r.json();
                deviceSelect.innerHTML = '<option value="">— Выберите устройство —</option>';
                if (r.ok && data.agents && data.agents.length > 0) {
                    data.agents.forEach(agent => {
                        const opt = document.createElement('option');
                        opt.value = agent.device_id;
                        opt.textContent = `${agent.device_id} (${agent.user_display_name || '—'})`;
                        deviceSelect.appendChild(opt);
                    });
                    const bulkDevicesEl = document.getElementById('agentUpdatesBulkDevices');
                    if (bulkDevicesEl) {
                        bulkDevicesEl.innerHTML = '';
                        data.agents.forEach(agent => {
                            const opt = document.createElement('option');
                            opt.value = agent.device_id;
                            opt.textContent = (agent.device_id || '').slice(0, 8) + '... (' + (agent.os_type || '—') + ')';
                            bulkDevicesEl.appendChild(opt);
                        });
                    }
                }
            } catch (e) {
                console.error('Agent updates: load agents', e);
            }

            loadAgentUpdatesBuilds(false);
        }

        async function triggerBulkAgentUpdate() {
            const bulkAllEl = document.getElementById('agentUpdatesBulkAllOnline');
            const bulkDevicesEl = document.getElementById('agentUpdatesBulkDevices');
            const channelEl = document.getElementById('agentUpdatesBulkChannel');
            const versionEl = document.getElementById('agentUpdatesBulkVersion');
            const rolloutModeEl = document.getElementById('agentUpdatesRolloutMode');
            const requireCanaryEl = document.getElementById('agentUpdatesRequireCanaryConfirm');
            const canaryConfirmedEl = document.getElementById('agentUpdatesCanaryConfirmed');
            const resultEl = document.getElementById('agentUpdatesBulkResult');
            const resultContent = document.getElementById('agentUpdatesBulkResultContent');
            const body = { channel: (channelEl && channelEl.value) || 'stable' };
            const rolloutMode = (rolloutModeEl && rolloutModeEl.value) || 'bulk';
            body.rollout_mode = rolloutMode;
            body.require_canary_confirmed = !!(requireCanaryEl && requireCanaryEl.checked);
            body.canary_confirmed = !!(canaryConfirmedEl && canaryConfirmedEl.checked);
            if (pendingCanaryOperationId || confirmedCanaryOperationId) {
                body.canary_operation_id = pendingCanaryOperationId || confirmedCanaryOperationId;
            }
            const v = (versionEl && versionEl.value) ? String(versionEl.value).trim() : '';
            if (v) body.version = v;
            if (!bulkAllEl || !bulkAllEl.checked) {
                const selected = bulkDevicesEl ? Array.from(bulkDevicesEl.selectedOptions || []).map(function(o) { return o.value; }).filter(Boolean) : [];
                body.device_ids = selected.length ? selected : null;
            } else {
                body.device_ids = null;
            }
            if (rolloutMode === 'canary') {
                const canaryDeviceIds = body.device_ids && body.device_ids.length ? body.device_ids : [];
                if (canaryDeviceIds.length === 0) {
                    resultEl.style.display = 'block';
                    resultContent.innerHTML = '<p class="error-message">Для canary выберите одно устройство (снимите галочку «Все онлайн»).</p>';
                    return;
                }
                body.device_ids = [canaryDeviceIds[0]];
            }
            if (resultEl) { resultEl.style.display = 'block'; resultContent.innerHTML = 'Отправка запроса...'; }
            try {
                const r = await fetch('/api/agents/update_bulk', {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify(body)
                });
                const data = await r.json();
                if (!r.ok) {
                    resultContent.innerHTML = '<p class="error-message">' + (data.error || 'Ошибка запроса') + '</p>';
                    return;
                }
                const ops = data.operations || [];
                const errs = data.errors || [];
                const skipped = data.skipped || [];
                setBulkPendingOperations(ops);
                if (ops.length === 0 && errs.length === 0) {
                    resultContent.innerHTML = '<p class="muted">Нет устройств для обновления (выберите устройства или «Все онлайн»).</p>';
                    return;
                }
                let msg = ops.length ? 'Запущено обновлений: ' + ops.length + '.' : '';
                if (errs.length) msg += ' Ошибки: ' + errs.length + ' (' + errs.map(function(e) { return e.device_id ? (e.device_id.slice(0, 8) + '...') : ''; }).join(', ') + ').';
                if (skipped.length) msg += ' Пропущено: ' + skipped.length + '.';
                resultContent.innerHTML = '<p>' + msg + ' Ожидание результатов...</p>';
                if (skipped.length) {
                    resultContent.innerHTML += '<div style="margin-top:8px;">' + skipped.map(function(item) {
                        return '<div><code>' + escapeHtml((item.device_id || '').slice(0, 8)) + '...</code> — <span class="muted">' + escapeHtml(item.reason || item.error_code || 'skipped') + '</span></div>';
                    }).join('') + '</div>';
                }
                if (rolloutMode === 'canary' && ops.length > 0 && canaryConfirmedEl) {
                    canaryConfirmedEl.checked = false;
                    confirmedCanaryOperationId = null;
                    pendingCanaryOperationId = ops[0].operation_id || null;
                }
                agentUpdatesBulkRows = ops;
                agentUpdatesBulkStatus = {};
                renderAgentUpdatesBulkResult();
                if (queueWs && queueWs.readyState === WebSocket.OPEN && ops.length) {
                    const deviceIds = {};
                    ops.forEach(function(o) { if (o.device_id) deviceIds[o.device_id] = true; });
                    Object.keys(deviceIds).forEach(function(deviceId) {
                        try { queueWs.send(JSON.stringify({ type: 'subscribe_device', device_id: deviceId })); } catch (e) {}
                    });
                }
            } catch (e) {
                resultContent.innerHTML = '<p class="error-message">Ошибка: ' + escapeHtml(e.message) + '</p>';
            }
        }

        async function loadAgentUpdatesBuilds(showLoading) {
            const loadingEl = document.getElementById('agentUpdatesBuildsLoading');
            const errorEl = document.getElementById('agentUpdatesBuildsError');
            const containerEl = document.getElementById('agentUpdatesBuildsContainer');
            const tbodyEl = document.getElementById('agentUpdatesBuildsTableBody');
            const buildSelect = document.getElementById('agentUpdatesBuildSelect');
            if (!tbodyEl || !buildSelect) return;

            if (showLoading !== false && loadingEl) loadingEl.style.display = 'block';
            if (errorEl) errorEl.style.display = 'none';

            try {
                const r = await fetch('/api/agent_builds?limit=100', { headers: getAuthHeaders() });
                const data = await r.json();
                if (loadingEl) loadingEl.style.display = 'none';

                if (!r.ok) {
                    if (errorEl) { errorEl.textContent = data.error || 'Ошибка загрузки билдов'; errorEl.style.display = 'block'; }
                    buildSelect.innerHTML = '<option value="">— Ошибка загрузки —</option>';
                    return;
                }

                const builds = data.builds || [];
                const valueSep = '|';

                buildSelect.innerHTML = '<option value="">— Выберите билд —</option>';
                builds.forEach(b => {
                    const val = [b.target, b.channel, b.version].join(valueSep);
                    const opt = document.createElement('option');
                    opt.value = val;
                    opt.textContent = `${b.target} / ${b.channel} / ${b.version}`;
                    buildSelect.appendChild(opt);
                });

                tbodyEl.innerHTML = builds.map(b => {
                    const sizeKb = b.size != null ? Math.round(b.size / 1024) + ' КБ' : '—';
                    const created = b.created_at ? new Date(b.created_at).toLocaleString('ru-RU') : '—';
                    return `<tr><td>${b.target}</td><td>${b.channel}</td><td>${b.version}</td><td>${sizeKb}</td><td>${created}</td></tr>`;
                }).join('');
                if (containerEl) containerEl.style.display = 'block';
            } catch (e) {
                if (loadingEl) loadingEl.style.display = 'none';
                if (errorEl) { errorEl.textContent = 'Ошибка: ' + e.message; errorEl.style.display = 'block'; }
                buildSelect.innerHTML = '<option value="">— Ошибка —</option>';
            }
        }

        async function triggerAgentUpdate() {
            const deviceSelect = document.getElementById('agentUpdatesDeviceSelect');
            const buildSelect = document.getElementById('agentUpdatesBuildSelect');
            const restartDelayEl = document.getElementById('agentUpdatesRestartDelay');
            const resultEl = document.getElementById('agentUpdatesResult');
            const resultContent = document.getElementById('agentUpdatesResultContent');
            const errorEl = document.getElementById('agentUpdatesError');

            const deviceId = deviceSelect && deviceSelect.value ? deviceSelect.value.trim() : '';
            const buildVal = buildSelect && buildSelect.value ? buildSelect.value : '';
            const valueSep = '|';
            const parts = buildVal.split(valueSep);

            if (!deviceId) {
                if (errorEl) { errorEl.textContent = 'Выберите устройство'; errorEl.style.display = 'block'; }
                if (resultEl) resultEl.style.display = 'none';
                return;
            }
            if (parts.length !== 3 || !parts[0]) {
                if (errorEl) { errorEl.textContent = 'Выберите билд агента'; errorEl.style.display = 'block'; }
                if (resultEl) resultEl.style.display = 'none';
                return;
            }

            const target = parts[0];
            const channel = parts[1];
            const version = parts[2];
            const restart_delay_sec = restartDelayEl ? parseInt(restartDelayEl.value, 10) : 2;
            const body = { target, channel, version };
            if (!isNaN(restart_delay_sec) && restart_delay_sec >= 0) body.restart_delay_sec = restart_delay_sec;

            if (errorEl) errorEl.style.display = 'none';
            if (resultEl) { resultEl.style.display = 'block'; resultContent.textContent = 'Отправка запроса...'; }

            try {
                const r = await fetch('/api/devices/' + encodeURIComponent(deviceId) + '/agent/update', {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify(body)
                });
                const data = await r.json();

                if (r.ok && data.status === 'accepted') {
                    const opId = data.operation_id || '';
                    const buildStr = data.build ? (data.build.target + ' / ' + data.build.channel + ' / ' + data.build.version) : '—';
                    resultContent.innerHTML = `
                        <p class="success-message">Обновление принято в очередь. Ожидание результата...</p>
                        <p><strong>ID операции:</strong> <code>${opId}</code></p>
                        <p><strong>Билд:</strong> ${buildStr}</p>
                    `;
                    if (typeof queueWs !== 'undefined' && queueWs && queueWs.readyState === WebSocket.OPEN && deviceId) {
                        try { queueWs.send(JSON.stringify({ type: 'subscribe_device', device_id: deviceId })); } catch (e) {}
                        if (typeof setPendingAgentUpdateOperation === 'function') setPendingAgentUpdateOperation(opId, deviceId);
                    }
                } else {
                    resultContent.innerHTML = `
                        <p class="error-message">${data.error || 'Ошибка запроса'}</p>
                        ${data.error_code ? `<p><code>${data.error_code}</code></p>` : ''}
                    `;
                }
            } catch (e) {
                resultContent.innerHTML = '<p class="error-message">Ошибка: ' + e.message + '</p>';
            }
        }

        function syncAgentBuildUploadArchiveType() {
            const fileInput = document.getElementById('agentBuildUploadFile');
            const archiveSelect = document.getElementById('agentBuildUploadArchiveType');
            if (!fileInput || !archiveSelect || !fileInput.files || !fileInput.files.length) return;
            const name = (fileInput.files[0].name || '').toLowerCase();
            if (name.endsWith('.zip')) archiveSelect.value = 'zip';
            else if (name.endsWith('.tar.gz') || name.endsWith('.tgz')) archiveSelect.value = 'tar.gz';
        }

        async function submitAgentBuildUpload(e) {
            e.preventDefault();
            const fileInput = document.getElementById('agentBuildUploadFile');
            const targetEl = document.getElementById('agentBuildUploadTarget');
            const channelEl = document.getElementById('agentBuildUploadChannel');
            const versionEl = document.getElementById('agentBuildUploadVersion');
            const archiveTypeEl = document.getElementById('agentBuildUploadArchiveType');
            const overwriteEl = document.getElementById('agentBuildUploadOverwrite');
            const resultEl = document.getElementById('agentBuildUploadResult');
            const errorEl = document.getElementById('agentBuildUploadError');
            const submitBtn = document.getElementById('agentBuildUploadSubmit');
            if (!fileInput || !fileInput.files || !fileInput.files[0] || !targetEl || !channelEl || !versionEl || !archiveTypeEl) return;
            const version = (versionEl.value || '').trim();
            if (!version) {
                if (errorEl) { errorEl.textContent = 'Укажите версию'; errorEl.style.display = 'block'; }
                if (resultEl) resultEl.style.display = 'none';
                return;
            }
            if (errorEl) errorEl.style.display = 'none';
            if (resultEl) { resultEl.style.display = 'block'; resultEl.textContent = 'Загрузка...'; }
            if (submitBtn) submitBtn.disabled = true;
            try {
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('target', targetEl.value);
                formData.append('channel', channelEl.value);
                formData.append('version', version);
                formData.append('archive_type', archiveTypeEl.value);
                if (overwriteEl && overwriteEl.checked) formData.append('overwrite', 'true');
                const r = await fetch('/api/agent_builds/upload', {
                    method: 'POST',
                    headers: { 'Authorization': (localStorage.getItem('admin_auth_token') || '') ? 'Bearer ' + localStorage.getItem('admin_auth_token') : '' },
                    body: formData
                });
                const data = await r.json();
                if (resultEl) {
                    resultEl.style.display = 'block';
                    if (r.ok && data.status === 'success') {
                        resultEl.innerHTML = '<p class="success-message">Билд загружен.</p><p><strong>' + (data.target || '') + ' / ' + (data.channel || '') + ' / ' + (data.version || '') + '</strong>, размер ' + (data.size ? Math.round(data.size / 1024) + ' КБ' : '—') + '</p>';
                        loadAgentUpdatesBuilds(true);
                        fileInput.value = '';
                        versionEl.value = '';
                    } else {
                        resultEl.innerHTML = '<p class="error-message">' + (data.error || 'Ошибка загрузки') + '</p>';
                    }
                }
            } catch (err) {
                if (resultEl) { resultEl.style.display = 'block'; resultEl.innerHTML = '<p class="error-message">Ошибка: ' + escapeHtml(err.message) + '</p>'; }
            } finally {
                if (submitBtn) submitBtn.disabled = false;
            }
        }

        // ============================================
        // Devices Tab Functions
        // ============================================

        let currentDeviceIdForTokens = null;
        const DEVICE_HASH_PREFIX = 'device-';
        const DEVICE_MODULE_CONSOLE_MAX = 80;

        function getDeviceModuleConsoleStore() {
            if (!window._deviceModuleConsole) window._deviceModuleConsole = {};
            return window._deviceModuleConsole;
        }

        function deviceModuleConsoleLog(deviceId, text, isError) {
            const store = getDeviceModuleConsoleStore();
            if (!store[deviceId]) store[deviceId] = [];
            store[deviceId].push({ time: Date.now(), text: text, isError: !!isError });
            const arr = store[deviceId];
            if (arr.length > DEVICE_MODULE_CONSOLE_MAX) arr.splice(0, arr.length - DEVICE_MODULE_CONSOLE_MAX);
            if (getDeviceIdFromHash() === deviceId) renderDeviceModuleConsole(deviceId);
        }

        function renderDeviceModuleConsole(deviceId) {
            const el = document.getElementById('deviceModuleConsole');
            if (!el) return;
            const store = getDeviceModuleConsoleStore();
            const messages = (store[deviceId] || []).slice(-50);
            if (messages.length === 0) {
                el.textContent = 'Нет сообщений. Действия с модулями и результаты появятся здесь.';
                el.style.color = '#888';
                return;
            }
            el.style.color = '';
            el.innerHTML = messages.map(function (m) {
                const timeStr = new Date(m.time).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                const cls = m.isError ? 'device-console-err' : 'device-console-ok';
                return '<div class="' + cls + '" style="margin-bottom: 4px;">[' + escapeHtml(timeStr) + '] ' + escapeHtml(m.text) + '</div>';
            }).join('');
            el.scrollTop = el.scrollHeight;
        }

        function getDeviceIdFromHash() {
            const h = (window.location.hash || '').slice(1);
            if (h.startsWith(DEVICE_HASH_PREFIX)) return h.slice(DEVICE_HASH_PREFIX.length);
            return null;
        }

        function setDeviceHash(deviceId) {
            window.location.hash = DEVICE_HASH_PREFIX + deviceId;
        }

        function clearDeviceHash() {
            if (window.location.hash.slice(1).startsWith(DEVICE_HASH_PREFIX)) {
                history.replaceState(null, '', window.location.pathname + window.location.search);
            }
        }

        function scheduleDeviceModulesRefreshAfterAction(deviceId) {
            [2000, 5000, 9000].forEach(function(ms) {
                setTimeout(function() {
                    if (getDeviceIdFromHash() === deviceId) refreshDeviceModulesOnly(deviceId);
                }, ms);
            });
        }

        async function refreshDeviceModulesOnly(deviceId) {
            if (!deviceId || getDeviceIdFromHash() !== deviceId) return;
            const installedWrap = document.getElementById('agentInstalledModulesWrap');
            if (!installedWrap) return;
            try {
                const modR = await fetch('/api/devices/' + encodeURIComponent(deviceId) + '/modules', { headers: getAuthHeaders() });
                const modData = await responseToJson(modR);
                if (getDeviceIdFromHash() !== deviceId) return;
                if (modR.ok && modData.modules && modData.modules.length) {
                    const rows = modData.modules.map(m => {
                        const state = m.active ? 'активен' : 'неактивен';
                        const mod = escapeHtml(m.module_name);
                        const ver = escapeHtml(m.version || '');
                        return '<tr><td><code>' + mod + '</code></td><td>' + ver + '</td><td>' + state + '</td><td><button type="button" class="btn btn-small btn-secondary agent-module-update" data-module="' + mod + '" data-version="' + ver + '">Обновить</button> <button type="button" class="btn btn-small btn-danger agent-module-remove" data-module="' + mod + '">Удалить</button></td></tr>';
                    }).join('');
                    installedWrap.innerHTML = '<p><strong>Установленные модули на агенте:</strong></p><table class="queue-table" style="max-width: 640px;"><thead><tr><th>Модуль</th><th>Версия</th><th>Состояние</th><th>Действия</th></tr></thead><tbody>' + rows + '</tbody></table>';
                } else {
                    installedWrap.innerHTML = '<p><strong>Установленные модули на агенте:</strong> нет данных или модулей нет.</p>';
                }
            } catch (e) {
                if (getDeviceIdFromHash() === deviceId) installedWrap.innerHTML = '<p><strong>Установленные модули на агенте:</strong> ошибка загрузки — ' + escapeHtml(e.message) + '</p>';
            }
        }

        function devicesApplyHash() {
            const deviceId = getDeviceIdFromHash();
            const listSection = document.getElementById('devicesListSection');
            const agentPanel = document.getElementById('deviceAgentPanel');
            const tokensSection = document.getElementById('deviceTokensSection');
            if (deviceId) {
                if (listSection) listSection.style.display = 'none';
                if (tokensSection) tokensSection.style.display = 'none';
                if (agentPanel) {
                    agentPanel.style.display = 'block';
                    loadDeviceAgentPage(deviceId);
                }
            } else {
                if (listSection) listSection.style.display = 'block';
                if (agentPanel) agentPanel.style.display = 'none';
            }
        }

        async function loadDeviceAgentPage(deviceId, silent) {
            const loadingEl = document.getElementById('deviceAgentLoading');
            const errorEl = document.getElementById('deviceAgentError');
            const contentEl = document.getElementById('deviceAgentContent');
            const titleEl = document.getElementById('deviceAgentTitle');
            if (!contentEl) return;
            if (!silent) {
                loadingEl.style.display = 'block';
                errorEl.style.display = 'none';
                contentEl.style.display = 'none';
            }
            titleEl.textContent = deviceId;

            try {
                const r = await fetch('/api/devices/' + encodeURIComponent(deviceId), { headers: getAuthHeaders() });
                const data = await responseToJson(r);
                if (!silent) loadingEl.style.display = 'none';
                if (!r.ok || data.status !== 'ok') {
                    if (!silent) {
                        errorEl.textContent = data.error || 'Не удалось загрузить данные устройства';
                        errorEl.style.display = 'block';
                    }
                    return;
                }
                const d = data.device;
                document.getElementById('agentHostname').textContent = d.hostname || '—';
                document.getElementById('agentDeviceId').textContent = d.device_id || '—';
                if (d.is_deleted) {
                    const archivedAt = d.deleted_at ? new Date(d.deleted_at).toLocaleString('ru-RU') : 'неизвестно';
                    document.getElementById('agentOnline').innerHTML = '<span style="color: #b42318;">Архивирован</span> <span style="color: #666;">(' + archivedAt + ')</span>';
                } else {
                    document.getElementById('agentOnline').innerHTML = d.online ? '<span style="color: green;">В сети</span>' : '<span style="color: #999;">Не в сети</span>';
                }
                document.getElementById('agentOs').textContent = d.os || '—';
                document.getElementById('agentVersion').textContent = d.agent_version || '—';
                const appliedWrap = document.getElementById('agentAppliedUpdateWrap');
                const appliedVal = document.getElementById('agentAppliedUpdateVersion');
                if (appliedWrap && appliedVal) {
                    if (d.applied_update_version) {
                        appliedWrap.style.display = '';
                        appliedVal.textContent = d.applied_update_version + (d.last_update_operation_id ? ' (операция ' + (d.last_update_operation_id || '').slice(0, 8) + '…)' : '');
                    } else {
                        appliedWrap.style.display = 'none';
                        appliedVal.textContent = '—';
                    }
                }
                document.getElementById('agentProtocol').textContent = d.protocol_version || '—';
                document.getElementById('agentToolsVersion').textContent = d.tools_version || '—';
                document.getElementById('agentToolsCount').textContent = d.tools_count != null ? d.tools_count : '—';
                document.getElementById('agentModulesCount').textContent = d.active_modules_count != null ? d.active_modules_count : '—';
                document.getElementById('agentFirstSeen').textContent = d.first_seen_at ? new Date(d.first_seen_at).toLocaleString('ru-RU') : '—';
                document.getElementById('agentLastSeen').textContent = d.last_seen_at ? new Date(d.last_seen_at).toLocaleString('ru-RU') : '—';
                document.getElementById('agentLastHandshake').textContent = d.last_handshake_at ? new Date(d.last_handshake_at).toLocaleString('ru-RU') : '—';

                const modulesWrap = document.getElementById('agentModulesListWrap');
                if (d.modules && d.modules.length) {
                    modulesWrap.innerHTML = '<p><strong>Модули (из handshake):</strong> ' + d.modules.map(m => '<code>' + escapeHtml(m) + '</code>').join(', ') + '</p>';
                } else {
                    modulesWrap.innerHTML = '<p><strong>Модули (из handshake):</strong> —</p>';
                }

                if (!silent) {
                    const installedWrap = document.getElementById('agentInstalledModulesWrap');
                    installedWrap.innerHTML = '<p class="loading">Загрузка установленных модулей...</p>';
                    try {
                        const modR = await fetch('/api/devices/' + encodeURIComponent(deviceId) + '/modules', { headers: getAuthHeaders() });
                        const modData = await responseToJson(modR);
                        if (modR.ok && modData.modules && modData.modules.length) {
                            const rows = modData.modules.map(m => {
                                const state = m.active ? 'активен' : 'неактивен';
                                const mod = escapeHtml(m.module_name);
                                const ver = escapeHtml(m.version || '');
                                return '<tr><td><code>' + mod + '</code></td><td>' + ver + '</td><td>' + state + '</td><td><button type="button" class="btn btn-small btn-secondary agent-module-update" data-module="' + mod + '" data-version="' + ver + '">Обновить</button> <button type="button" class="btn btn-small btn-danger agent-module-remove" data-module="' + mod + '">Удалить</button></td></tr>';
                            }).join('');
                            installedWrap.innerHTML = '<p><strong>Установленные модули на агенте:</strong></p><table class="queue-table" style="max-width: 640px;"><thead><tr><th>Модуль</th><th>Версия</th><th>Состояние</th><th>Действия</th></tr></thead><tbody>' + rows + '</tbody></table>';
                            deviceModuleConsoleLog(deviceId, 'Загружены модули: ' + modData.modules.length + ' шт.', false);
                        } else {
                            installedWrap.innerHTML = '<p><strong>Установленные модули на агенте:</strong> нет данных или модулей нет.</p>';
                            deviceModuleConsoleLog(deviceId, 'Модулей на агенте нет или ответ пуст.', false);
                        }
                    } catch (e) {
                        installedWrap.innerHTML = '<p><strong>Установленные модули на агенте:</strong> ошибка загрузки — ' + escapeHtml(e.message) + '</p>';
                        deviceModuleConsoleLog(deviceId, 'Ошибка загрузки модулей: ' + e.message, true);
                    }
                    renderDeviceModuleConsole(deviceId);
                    const installLink = document.getElementById('deviceAgentInstallModuleLink');
                    if (installLink) {
                        installLink.href = '#';
                        installLink.onclick = function(e) { e.preventDefault(); setDeviceIdForModulesTab(deviceId); switchTab('modules'); };
                    }
                }
                if (!silent) contentEl.style.display = 'block';
            } catch (e) {
                if (!silent) {
                    loadingEl.style.display = 'none';
                    errorEl.textContent = 'Ошибка: ' + e.message;
                    errorEl.style.display = 'block';
                }
            }
        }

        function escapeHtml(s) {
            const div = document.createElement('div');
            div.textContent = s;
            return div.innerHTML;
        }

        function setDeviceIdForModulesTab(deviceId) {
            window._selectedDeviceIdForModules = deviceId;
        }

        async function deviceAgentRefresh() {
            const deviceId = getDeviceIdFromHash();
            if (!deviceId) return;
            const btn = document.getElementById('deviceAgentRefreshBtn');
            if (btn) btn.disabled = true;
            deviceModuleConsoleLog(deviceId, 'Запрос данных с агента...', false);
            try {
                const r = await fetch('/api/devices/' + encodeURIComponent(deviceId) + '/check', {
                    method: 'POST',
                    headers: getAuthHeaders(true)
                });
                const data = await responseToJson(r);
                if (r.ok && data.status === 'ok') {
                    deviceModuleConsoleLog(deviceId, 'Данные с агента обновлены.', false);
                    renderDeviceModuleConsole(deviceId);
                    // Периодически подгружаем данные — страница сама обновит поля без перезагрузки
                    const pollCount = 5;
                    const pollIntervalMs = 2000;
                    let attempts = 0;
                    function poll() {
                        attempts++;
                        loadDeviceAgentPage(deviceId, true);
                        if (attempts < pollCount) setTimeout(poll, pollIntervalMs);
                        if (btn) btn.disabled = false;
                    }
                    setTimeout(poll, pollIntervalMs);
                } else {
                    const msg = data.error || 'Ошибка запроса';
                    deviceModuleConsoleLog(deviceId, msg, true);
                    renderDeviceModuleConsole(deviceId);
                    alert(msg);
                    if (btn) btn.disabled = false;
                }
            } catch (e) {
                deviceModuleConsoleLog(deviceId, 'Ошибка: ' + e.message, true);
                renderDeviceModuleConsole(deviceId);
                alert('Ошибка: ' + e.message);
                if (btn) btn.disabled = false;
            }
        }

        (function initDeviceAgentPanel() {
            const backLink = document.getElementById('deviceAgentBackLink');
            if (backLink) {
                backLink.addEventListener('click', function(e) {
                    e.preventDefault();
                    clearDeviceHash();
                    document.getElementById('devicesListSection').style.display = 'block';
                    document.getElementById('deviceAgentPanel').style.display = 'none';
                    loadDevicesList();
                });
            }
            const refreshBtn = document.getElementById('deviceAgentRefreshBtn');
            if (refreshBtn) refreshBtn.addEventListener('click', deviceAgentRefresh);
            const tokensBtn = document.getElementById('deviceAgentTokensBtn');
            if (tokensBtn) {
                tokensBtn.addEventListener('click', function() {
                    const deviceId = getDeviceIdFromHash();
                    if (deviceId) { currentDeviceIdForTokens = deviceId; viewDeviceTokens(deviceId); document.getElementById('deviceTokensSection').style.display = 'block'; }
                });
            }
            const agentPanel = document.getElementById('deviceAgentPanel');
            if (agentPanel) {
                agentPanel.addEventListener('click', function(e) {
                    const removeBtn = e.target.closest('.agent-module-remove');
                    const updateBtn = e.target.closest('.agent-module-update');
                    if (removeBtn) { e.preventDefault(); agentModuleRemove(removeBtn.getAttribute('data-module')); }
                    if (updateBtn) { e.preventDefault(); agentModuleUpdate(updateBtn.getAttribute('data-module'), updateBtn.getAttribute('data-version')); }
                });
            }
            window.addEventListener('hashchange', function() {
                if (document.querySelector('#tab-devices.active')) devicesApplyHash();
            });
        })();

        async function agentModuleRemove(moduleName) {
            const deviceId = getDeviceIdFromHash();
            if (!deviceId || !moduleName) return;
            if (!confirm('Удалить модуль «' + moduleName + '» с агента?')) return;
            try {
                const r = await fetch('/api/devices/' + encodeURIComponent(deviceId) + '/modules/remove', {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({ module_name: moduleName })
                });
                const data = await responseToJson(r);
                if (r.ok && (data.status === 'accepted' || data.status === 'ok')) {
                    deviceModuleConsoleLog(deviceId, 'Модуль «' + moduleName + '» удалён.', false);
                    renderDeviceModuleConsole(deviceId);
                    scheduleDeviceModulesRefreshAfterAction(deviceId);
                } else {
                    const msg = data.error || 'Ошибка';
                    deviceModuleConsoleLog(deviceId, 'Ошибка удаления «' + moduleName + '»: ' + msg, true);
                    renderDeviceModuleConsole(deviceId);
                    alert(msg);
                }
            } catch (e) {
                deviceModuleConsoleLog(deviceId, 'Ошибка удаления «' + moduleName + '»: ' + e.message, true);
                renderDeviceModuleConsole(deviceId);
                alert('Ошибка: ' + e.message);
            }
        }

        async function agentModuleUpdate(moduleName, version) {
            const deviceId = getDeviceIdFromHash();
            if (!deviceId || !moduleName) return;
            if (!version) { alert('Версия модуля неизвестна.'); return; }
            try {
                const r = await fetch('/api/devices/' + encodeURIComponent(deviceId) + '/modules/install', {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({ module_name: moduleName, version: version })
                });
                const data = await responseToJson(r);
                if (r.ok && (data.status === 'accepted' || data.status === 'ok')) {
                    deviceModuleConsoleLog(deviceId, 'Модуль «' + moduleName + '» ' + version + ' установлен/обновлён.', false);
                    renderDeviceModuleConsole(deviceId);
                    scheduleDeviceModulesRefreshAfterAction(deviceId);
                } else {
                    const msg = data.error || 'Ошибка';
                    deviceModuleConsoleLog(deviceId, 'Ошибка установки «' + moduleName + '» ' + version + ': ' + msg, true);
                    renderDeviceModuleConsole(deviceId);
                    alert(msg);
                }
            } catch (e) {
                deviceModuleConsoleLog(deviceId, 'Ошибка установки «' + moduleName + '»: ' + e.message, true);
                renderDeviceModuleConsole(deviceId);
                alert('Ошибка: ' + e.message);
            }
        }

        async function loadDevicesList() {
            const loadingEl = document.getElementById('devicesListLoading');
            const errorEl = document.getElementById('devicesListError');
            const containerEl = document.getElementById('devicesListContainer');
            const tbodyEl = document.getElementById('devicesListTableBody');
            const bulkBar = document.getElementById('devicesBulkBar');
            const selectAllCb = document.getElementById('devicesSelectAll');

            loadingEl.style.display = 'block';
            errorEl.style.display = 'none';
            containerEl.style.display = 'none';
            if (bulkBar) bulkBar.style.display = 'none';

            try {
                const response = await fetch('/api/devices', { headers: getAuthHeaders() });
                const data = await response.json();

                if (data.status === 'ok' && data.devices) {
                    loadingEl.style.display = 'none';
                    containerEl.style.display = 'block';

                    if (data.devices.length === 0) {
                        tbodyEl.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 20px;">Устройств не найдено</td></tr>';
                    } else {
                        tbodyEl.innerHTML = data.devices.map(device => {
                            const hostname = (device.hostname && device.hostname.trim()) ? escapeHtml(device.hostname) : '—';
                            const hostnameLink = '<a href="#" class="device-hostname-link" data-device-id="' + escapeHtml(device.device_id) + '">' + hostname + '</a>';
                            const status = device.online ? '<span style="color: green;">В сети</span>' : '<span style="color: #999;">Не в сети</span>';
                            const lastActivity = device.last_seen_at ? new Date(device.last_seen_at).toLocaleString('ru-RU') : '—';
                            const did = escapeHtml(device.device_id);
                            return `<tr>
                                <td><input type="checkbox" class="device-row-cb" value="${did}" data-device-id="${did}"></td>
                                <td>${hostnameLink}</td>
                                <td>${status}</td>
                                <td>${lastActivity}</td>
                                <td>
                                    <div class="dropdown-actions">
                                        <button type="button" class="btn btn-small btn-secondary dropdown-trigger">Действия ▾</button>
                                        <ul class="dropdown-menu">
                                            <li><a href="#" class="device-action-check" data-device-id="${did}">Проверить устройство</a></li>
                                            <li><a href="#" class="device-action-modules" data-device-id="${did}">Список модулей</a></li>
                                            <li><a href="#" class="device-action-install" data-device-id="${did}">Установить модуль</a></li>
                                            <li><a href="#" class="device-action-tokens" data-device-id="${did}">Токены устройства</a></li>
                                            <li><a href="#" class="device-action-delete" data-device-id="${did}">Архивировать агента</a></li>
                                        </ul>
                                    </div>
                                </td>
                            </tr>`;
                        }).join('');
                        if (bulkBar) bulkBar.style.display = 'block';
                        bindDevicesListHandlers();
                    }
                    if (selectAllCb) selectAllCb.checked = false;
                } else {
                    throw new Error(data.error || 'Не удалось загрузить список устройств');
                }
            } catch (error) {
                loadingEl.style.display = 'none';
                errorEl.textContent = 'Ошибка: ' + error.message;
                errorEl.style.display = 'block';
            }
        }

        function bindDevicesListHandlers() {
            document.querySelectorAll('.device-hostname-link').forEach(a => {
                a.addEventListener('click', function(e) {
                    e.preventDefault();
                    const id = this.getAttribute('data-device-id');
                    if (id) setDeviceHash(id);
                    devicesApplyHash();
                });
            });
            document.querySelectorAll('.device-action-check').forEach(a => {
                a.addEventListener('click', function(e) { e.preventDefault(); deviceActionCheck(this.getAttribute('data-device-id')); });
            });
            document.querySelectorAll('.device-action-modules').forEach(a => {
                a.addEventListener('click', function(e) { e.preventDefault(); const id = this.getAttribute('data-device-id'); setDeviceHash(id); devicesApplyHash(); });
            });
            document.querySelectorAll('.device-action-install').forEach(a => {
                a.addEventListener('click', function(e) { e.preventDefault(); setDeviceIdForModulesTab(this.getAttribute('data-device-id')); switchTab('modules'); });
            });
            document.querySelectorAll('.device-action-tokens').forEach(a => {
                a.addEventListener('click', function(e) { e.preventDefault(); viewDeviceTokens(this.getAttribute('data-device-id')); });
            });
            document.querySelectorAll('.device-action-delete').forEach(a => {
                a.addEventListener('click', function(e) { e.preventDefault(); deviceActionDelete(this.getAttribute('data-device-id')); });
            });
            const selectAll = document.getElementById('devicesSelectAll');
            if (selectAll) {
                selectAll.onclick = function() {
                    document.querySelectorAll('.device-row-cb').forEach(cb => { cb.checked = this.checked; });
                    devicesUpdateBulkCount();
                };
            }
            document.querySelectorAll('.device-row-cb').forEach(cb => {
                cb.addEventListener('change', devicesUpdateBulkCount);
            });
            const bulkDeselect = document.getElementById('devicesBulkDeselect');
            if (bulkDeselect) bulkDeselect.addEventListener('click', function() {
                document.querySelectorAll('.device-row-cb').forEach(c => { c.checked = false; });
                const sa = document.getElementById('devicesSelectAll'); if (sa) sa.checked = false;
                devicesUpdateBulkCount();
            });
            const bulkRefresh = document.getElementById('devicesBulkRefresh');
            if (bulkRefresh) bulkRefresh.addEventListener('click', devicesBulkRefresh);
            const bulkDelete = document.getElementById('devicesBulkDelete');
            if (bulkDelete) bulkDelete.addEventListener('click', devicesBulkDelete);
            document.querySelectorAll('.dropdown-trigger').forEach(btn => {
                btn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    const menu = this.nextElementSibling;
                    document.querySelectorAll('.dropdown-menu').forEach(m => { if (m !== menu) m.classList.remove('open'); });
                    menu.classList.toggle('open');
                });
            });
            document.addEventListener('click', function() {
                document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.remove('open'));
            });
        }

        function devicesUpdateBulkCount() {
            const n = document.querySelectorAll('.device-row-cb:checked').length;
            const el = document.getElementById('devicesBulkCount');
            if (el) el.textContent = 'Выбрано: ' + n;
        }

        async function deviceActionCheck(deviceId) {
            try {
                const r = await fetch('/api/devices/' + encodeURIComponent(deviceId) + '/check', {
                    method: 'POST',
                    headers: getAuthHeaders(true)
                });
                const data = await responseToJson(r);
                if (r.ok && data.status === 'ok') {
                    alert('Запрос проверки отправлен. Данные обновятся после ответа агента.');
                    loadDevicesList();
                } else {
                    alert(data.error || 'Ошибка');
                }
            } catch (e) {
                alert('Ошибка: ' + e.message);
            }
        }

        async function deviceActionDelete(deviceId) {
            if (!confirm('Архивировать агента ' + deviceId + '? Агент исчезнет из активных списков, токены будут отозваны, текущие команды остановлены. История и тикеты сохранятся.')) return;
            try {
                const r = await fetch('/api/devices/' + encodeURIComponent(deviceId), {
                    method: 'DELETE',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({})
                });
                const data = await responseToJson(r);
                if (r.ok && data.status === 'ok') {
                    clearDeviceHash();
                    loadDevicesList();
                    alert(data.message || 'Агент архивирован.');
                } else {
                    alert(data.error || 'Ошибка');
                }
            } catch (e) {
                alert('Ошибка: ' + e.message);
            }
        }

        async function devicesBulkRefresh() {
            const ids = Array.from(document.querySelectorAll('.device-row-cb:checked')).map(cb => cb.getAttribute('data-device-id')).filter(Boolean);
            if (ids.length === 0) { alert('Выберите хотя бы одно устройство.'); return; }
            let ok = 0, fail = 0;
            for (const deviceId of ids) {
                try {
                    const r = await fetch('/api/devices/' + encodeURIComponent(deviceId) + '/check', {
                        method: 'POST',
                        headers: getAuthHeaders(true)
                    });
                    const data = await responseToJson(r);
                    if (r.ok && data.status === 'ok') ok++; else fail++;
                } catch (e) { fail++; }
            }
            loadDevicesList();
            alert('Запрос проверки отправлен: ' + ok + ' устройств. Не в сети или ошибка: ' + fail);
        }

        async function devicesBulkDelete() {
            const ids = Array.from(document.querySelectorAll('.device-row-cb:checked')).map(cb => cb.getAttribute('data-device-id')).filter(Boolean);
            if (ids.length === 0) { alert('Выберите хотя бы одно устройство.'); return; }
            if (!confirm('Архивировать выбранные агенты (' + ids.length + ')? Они исчезнут из активных списков, но история по ним сохранится.')) return;
            let ok = 0, fail = 0;
            for (const deviceId of ids) {
                try {
                    const r = await fetch('/api/devices/' + encodeURIComponent(deviceId), {
                        method: 'DELETE',
                        headers: getAuthHeaders(true),
                        body: JSON.stringify({})
                    });
                    const data = await responseToJson(r);
                    if (r.ok && data.status === 'ok') ok++; else fail++;
                } catch (e) { fail++; }
            }
            clearDeviceHash();
            loadDevicesList();
            alert('Архивировано: ' + ok + '. Ошибок: ' + fail);
        }

        async function viewDeviceTokens(deviceId) {
            currentDeviceIdForTokens = deviceId;
            const sectionEl = document.getElementById('deviceTokensSection');
            const loadingEl = document.getElementById('deviceTokensLoading');
            const errorEl = document.getElementById('deviceTokensError');
            const containerEl = document.getElementById('deviceTokensContainer');
            const tbodyEl = document.getElementById('deviceTokensTableBody');

            sectionEl.style.display = 'block';
            loadingEl.style.display = 'block';
            errorEl.style.display = 'none';
            containerEl.style.display = 'none';

            try {
                const response = await fetch(`/api/devices/${deviceId}/tokens`, { headers: getAuthHeaders() });
                const data = await response.json();

                if (data.status === 'success' && data.tokens) {
                    loadingEl.style.display = 'none';
                    containerEl.style.display = 'block';

                    if (data.tokens.length === 0) {
                        tbodyEl.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 20px;">Токенов нет</td></tr>';
                    } else {
                        tbodyEl.innerHTML = data.tokens.map(token => `
                            <tr>
                                <td><code>${token.token_prefix}...</code></td>
                                <td>${token.created_at ? new Date(token.created_at).toLocaleString('ru-RU') : '—'}</td>
                                <td>${token.expires_at ? new Date(token.expires_at).toLocaleString('ru-RU') : 'Бессрочно'}</td>
                                <td>${token.last_used_at ? new Date(token.last_used_at).toLocaleString('ru-RU') : '—'}</td>
                                <td>
                                    ${token.is_active 
                                        ? '<span style="color: green;">Активен</span>' 
                                        : '<span style="color: #999;">Отозван/истёк</span>'}
                                </td>
                                <td>
                                    ${token.is_active 
                                        ? `<button class="btn btn-danger btn-small" onclick="revokeToken('${token.token_hash}')">Отозвать</button>`
                                        : '<span style="color: #8e8e93;">Уже отозван</span>'}
                                </td>
                            </tr>
                        `).join('');
                    }
                } else {
                    throw new Error(data.error || 'Не удалось загрузить токены');
                }
            } catch (error) {
                loadingEl.style.display = 'none';
                errorEl.textContent = 'Ошибка: ' + error.message;
                errorEl.style.display = 'block';
            }
        }

        async function revokeToken(tokenHash) {
            if (!confirm('Отозвать этот токен? Устройство не сможет подключаться с ним.')) {
                return;
            }

            if (!currentDeviceIdForTokens) {
                alert('Устройство не выбрано');
                return;
            }

            try {
                const response = await fetch(`/api/devices/${currentDeviceIdForTokens}/tokens/revoke`, {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({
                        token_hash: tokenHash
                    })
                });

                const data = await response.json();

                if (response.ok && data.status === 'success') {
                    alert('Токен отозван');
                    viewDeviceTokens(currentDeviceIdForTokens);
                } else {
                    alert('Ошибка: ' + (data.error || 'Не удалось отозвать токен'));
                }
            } catch (error) {
                alert('Ошибка: ' + error.message);
            }
        }

        async function generateTokenDevices() {
            const deviceUuid = document.getElementById('deviceUuidInputDevices').value.trim();
            const tokenError = document.getElementById('tokenErrorDevices');
            const tokenResult = document.getElementById('tokenResultDevices');
            const generatedToken = document.getElementById('generatedTokenDevices');
            
            tokenError.style.display = 'none';
            tokenResult.style.display = 'none';
            
            if (!deviceUuid) {
                tokenError.textContent = 'Введите UUID устройства';
                tokenError.style.display = 'block';
                return;
            }
            
            const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
            if (!uuidRegex.test(deviceUuid)) {
                tokenError.textContent = 'Неверный формат UUID';
                tokenError.style.display = 'block';
                return;
            }
            
            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        uuid: deviceUuid
                    })
                });
                
                const data = await response.json();
                
                if (response.ok && data.status === 'success') {
                    generatedToken.value = data.token;
                    tokenResult.style.display = 'block';
                    // Reload devices list and tokens if viewing
                    loadDevicesList();
                    if (currentDeviceIdForTokens === deviceUuid) {
                        viewDeviceTokens(deviceUuid);
                    }
                } else {
                    tokenError.textContent = data.error || 'Не удалось сгенерировать токен';
                    tokenError.style.display = 'block';
                }
            } catch (error) {
                tokenError.textContent = 'Ошибка: ' + error.message;
                tokenError.style.display = 'block';
            }
        }

        function clearTokenFormDevices() {
            document.getElementById('deviceUuidInputDevices').value = '';
            document.getElementById('tokenErrorDevices').style.display = 'none';
            document.getElementById('tokenResultDevices').style.display = 'none';
        }

        function copyTokenDevices() {
            const tokenInput = document.getElementById('generatedTokenDevices');
            tokenInput.select();
            tokenInput.setSelectionRange(0, 99999);
            try {
                document.execCommand('copy');
                alert('Токен скопирован в буфер обмена.');
            } catch (err) {
                console.error('Failed to copy token:', err);
            }
        }

        // ============================================
        // Modules Tab Functions
        // ============================================

        let modulesDataTab = [];
        let devicesDataTab = [];
        let selectedDeviceIdTab = null;

        async function loadModulesTab() {
            await Promise.all([
                loadDevicesListModules(),
                loadModulesList()
            ]);
        }

        function modulesInstallConsoleLog(message, isError) {
            const consoleEl = document.getElementById('modules-install-console');
            if (!consoleEl) return;
            const row = document.createElement('div');
            row.className = isError ? 'log-error' : 'log-line';
            row.textContent = message;
            consoleEl.appendChild(row);
            consoleEl.scrollTop = consoleEl.scrollHeight;
        }

        function renderDevicesListModules() {
            const tbody = document.getElementById('devices-table-modules-body');
            const checkboxesWrap = document.getElementById('devices-checkboxes-modules');
            const select = document.getElementById('deploy-device-modules');
            if (!tbody || !checkboxesWrap || !select) return;

            const currentValue = selectedDeviceIdTab || select.value;
            tbody.innerHTML = '';
            checkboxesWrap.innerHTML = '';
            select.innerHTML = '<option value="">Выберите устройство...</option>';

            (devicesDataTab || []).forEach(device => {
                const deviceId = device.device_id || '';
                const hostname = device.hostname || 'unknown';
                const status = device.online ? 'online' : 'offline';
                const statusLabel = device.online ? 'В сети' : 'Не в сети';
                const modulesCount = device.active_modules_count ?? 0;
                const toolCount = device.tools_count ?? 0;

                const row = document.createElement('tr');
                row.dataset.deviceId = deviceId;
                row.innerHTML = `
                    <td><input type="checkbox" class="modules-device-cb" value="${escapeHtml(deviceId)}"></td>
                    <td><code>${escapeHtml(deviceId)}</code></td>
                    <td>${escapeHtml(hostname)}</td>
                    <td><span class="badge badge-${status === 'online' ? 'active' : 'removed'}">${escapeHtml(statusLabel)}</span></td>
                    <td>${escapeHtml(device.os || '?')}</td>
                    <td>${modulesCount}</td>
                    <td>${toolCount}</td>
                    <td><button type="button" class="btn btn-small btn-secondary modules-open-device-btn" data-device-id="${escapeHtml(deviceId)}">Открыть</button></td>
                `;
                tbody.appendChild(row);

                const compactItem = document.createElement('label');
                compactItem.style.display = 'inline-flex';
                compactItem.style.alignItems = 'center';
                compactItem.style.gap = '8px';
                compactItem.style.marginRight = '12px';
                compactItem.innerHTML = `
                    <input type="checkbox" class="modules-device-cb" value="${escapeHtml(deviceId)}">
                    <span>${escapeHtml(hostname)} (${escapeHtml(deviceId.slice(0, 8))}...)</span>
                `;
                checkboxesWrap.appendChild(compactItem);

                const option = document.createElement('option');
                option.value = deviceId;
                option.textContent = `${hostname} (${deviceId})`;
                select.appendChild(option);
            });

            if (currentValue && (devicesDataTab || []).some(device => device.device_id === currentValue)) {
                select.value = currentValue;
            }
        }

        async function loadDevicesListModules() {
            const wrap = document.getElementById('devices-table-modules-wrap');
            const loadingEl = document.getElementById('devices-table-modules-loading');
            const tableEl = document.getElementById('devices-table-modules');
            const tbody = document.getElementById('devices-table-modules-body');
            if (loadingEl) loadingEl.style.display = 'block';
            if (tableEl) tableEl.style.display = 'none';
            if (tbody) tbody.innerHTML = '';
            try {
                const response = await fetch('/api/devices', { headers: getAuthHeaders() });
                const data = await responseToJson(response);
                if (loadingEl) loadingEl.style.display = 'none';
                if (!response.ok || data.status !== 'ok') {
                    if (tableEl) tableEl.style.display = 'block';
                    if (tbody) {
                        tbody.innerHTML = '<tr><td colspan="8"><div class="error-message">Не удалось загрузить устройства</div></td></tr>';
                    }
                    return;
                }

                devicesDataTab = data.devices || [];
                if (tableEl) tableEl.style.display = 'table';
                renderDevicesListModules();

                const selected = selectedDeviceIdTab || document.getElementById('deploy-device-modules')?.value;
                if (selected) {
                    selectDeviceModules(selected, true);
                }
            } catch (error) {
                if (loadingEl) loadingEl.style.display = 'none';
                if (tableEl) tableEl.style.display = 'table';
                if (tbody) {
                    tbody.innerHTML = `<tr><td colspan="8"><div class="error-message">Ошибка: ${escapeHtml(error.message)}</div></td></tr>`;
                }
            }
        }

        function selectDeviceModules(deviceId, silent) {
            const select = document.getElementById('deploy-device-modules');
            const details = document.getElementById('device-details-modules');
            selectedDeviceIdTab = deviceId || null;
            if (select && deviceId) {
                select.value = deviceId;
            }
            document.querySelectorAll('#devices-table-modules-body tr').forEach(row => {
                row.classList.toggle('selected', row.dataset.deviceId === deviceId);
            });
            if (!deviceId) {
                if (details) details.style.display = 'none';
                return;
            }
            if (details) details.style.display = 'block';
            if (!silent) {
                loadDeviceDetailsModules(deviceId);
            } else {
                loadDeviceDetailsModules(deviceId);
            }
        }

        function initRegistryModulesToggles() {
            const btnUpload = document.getElementById('registry-btn-upload-modules');
            const btnServer = document.getElementById('registry-btn-server-modules');
            const sectionUpload = document.getElementById('registry-upload-section');
            const sectionServer = document.getElementById('registry-server-section');
            if (!btnUpload || !btnServer || !sectionUpload || !sectionServer) return;

            function toggleSection(section, btn, otherSection, otherBtn) {
                const isOpen = section.style.display !== 'none';
                section.style.display = isOpen ? 'none' : 'block';
                btn.setAttribute('aria-expanded', !isOpen);
                if (!isOpen && section === sectionServer) {
                    loadModulesList();
                }
            }

            btnUpload.addEventListener('click', () => toggleSection(sectionUpload, btnUpload, sectionServer, btnServer));
            btnServer.addEventListener('click', () => toggleSection(sectionServer, btnServer, sectionUpload, btnUpload));
        }

        async function loadModulesList() {
            const container = document.getElementById('modules-list-modules');
            container.innerHTML = '<div class="loading">Загрузка модулей...</div>';

            try {
                const response = await fetch('/api/modules', { headers: getAuthHeaders() });
                const data = await response.json();

                if (data.modules) {
                    modulesDataTab = data.modules;
                    renderModulesList();
                    updateDeployModuleSelect();
                } else {
                    container.innerHTML = '<div class="error-message">Не удалось загрузить модули</div>';
                }
            } catch (error) {
                container.innerHTML = `<div class="error-message">Ошибка: ${escapeHtml(error.message)}</div>`;
            }
        }

        function renderModulesList() {
            const container = document.getElementById('modules-list-modules');
            if (modulesDataTab.length === 0) {
                container.innerHTML = '<div class="empty">Нет загруженных модулей</div>';
                return;
            }
            container.innerHTML = `
                <table>
                    <thead>
                        <tr>
                            <th>Модуль</th>
                            <th>Версия</th>
                            <th>Manifest</th>
                            <th>Platforms</th>
                            <th>Tools</th>
                            <th>Validation</th>
                            <th>Загружен</th>
                            <th>Действия</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${modulesDataTab.map(m => `
                            <tr>
                                <td><strong>${escapeHtml(m.module_name)}</strong>${m.legacy_manifest ? ' <span class="badge badge-warning">legacy</span>' : ''}</td>
                                <td>${escapeHtml(m.version)}</td>
                                <td>v${escapeHtml(String(m.manifest_version || '1'))}</td>
                                <td>${escapeHtml((m.platforms || []).join(', ') || 'any')}</td>
                                <td>${m.tools_count || 0}</td>
                                <td>${escapeHtml(m.validation_status || 'unknown')}</td>
                                <td>${m.created_at ? new Date(m.created_at).toLocaleString() : '?'}</td>
                                <td>
                                    <button type="button" class="btn btn-small" data-module-name="${escapeHtml(m.module_name)}" data-version="${escapeHtml(m.version)}" onclick="showInstallDialogModules(this)">Установить...</button>
                                    <button type="button" class="btn btn-small btn-secondary" data-module-name="${escapeHtml(m.module_name)}" data-version="${escapeHtml(m.version)}" onclick="showModuleDetailModules(this)">Details</button>
                                    <button type="button" class="btn btn-small btn-secondary" data-module-name="${escapeHtml(m.module_name)}" data-version="${escapeHtml(m.version)}" onclick="openUploadForUpdateModules(this)">Обновить</button>
                                    <button type="button" class="btn btn-small btn-danger" data-module-name="${escapeHtml(m.module_name)}" data-version="${escapeHtml(m.version)}" onclick="deleteModuleFromServerModules(this)">Удалить</button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }

        async function showModuleDetailModules(btn) {
            const name = btn.getAttribute('data-module-name');
            const version = btn.getAttribute('data-version');
            if (!name || !version) return;
            const wrap = document.getElementById('module-detail-modules');
            const content = document.getElementById('module-detail-content-modules');
            if (!wrap || !content) return;
            wrap.style.display = 'block';
            content.innerHTML = '<div class="loading">Загрузка деталей...</div>';
            try {
                const response = await fetch(`/api/modules/${encodeURIComponent(name)}/${encodeURIComponent(version)}`, { headers: getAuthHeaders() });
                const data = await response.json();
                if (!response.ok || data.status !== 'ok') {
                    content.innerHTML = `<div class="error-message">${escapeHtml(data.error || 'Не удалось загрузить детали модуля')}</div>`;
                    return;
                }
                content.innerHTML = `
                    <div class="toolset-info">
                        <div class="info-card"><label>Validation</label><value>${escapeHtml(data.validation_status || 'unknown')}</value></div>
                        <div class="info-card"><label>Manifest</label><value>v${escapeHtml(String(data.manifest_version || '1'))}</value></div>
                        <div class="info-card"><label>Platforms</label><value>${escapeHtml((data.platforms || []).join(', ') || 'any')}</value></div>
                        <div class="info-card"><label>Tools</label><value>${(data.tools || []).length}</value></div>
                    </div>
                    ${renderErrorInfoModules(data.validation_json)}
                    <div class="section"><h4>Tools Contract</h4><pre>${escapeHtml(JSON.stringify(data.tools || [], null, 2))}</pre></div>
                    <div class="section"><h4>Manifest JSON</h4><pre>${escapeHtml(JSON.stringify(data.manifest_json || {}, null, 2))}</pre></div>
                    <div class="section"><h4>Validation JSON</h4><pre>${escapeHtml(JSON.stringify(data.validation_json || {}, null, 2))}</pre></div>
                `;
            } catch (error) {
                content.innerHTML = `<div class="error-message">${escapeHtml(error.message)}</div>`;
            }
        }

        function renderErrorInfoModules(validationJson) {
            if (!validationJson) return '';
            const warnings = validationJson.warnings || [];
            const errors = validationJson.errors || {};
            const errorItems = Object.entries(errors).flatMap(([section, items]) => (items || []).map(item => `${section}: ${item}`));
            return `
                    <div class="section">
                        <h4>Validation Summary</h4>
                        ${warnings.length ? `<div class="preflight-warning" style="display:block;">Warnings:<br>${warnings.map(w => escapeHtml(w)).join('<br>')}</div>` : ''}
                        ${errorItems.length ? `<div class="error-message" style="display:block;">${errorItems.map(item => escapeHtml(item)).join('<br>')}</div>` : ''}
                    </div>
            `;
        }

        async function deleteModuleFromServerModules(btn) {
            const name = btn.getAttribute('data-module-name');
            const version = btn.getAttribute('data-version');
            if (!name || !version || !confirm(`Удалить модуль "${name}" версии ${version} с сервера? Это действие необратимо.`)) return;
            try {
                const response = await fetch(`/api/modules/${encodeURIComponent(name)}/${encodeURIComponent(version)}`, {
                    method: 'DELETE',
                    headers: getAuthHeaders()
                });
                const data = await response.json();
                if (response.ok && (data.status === 'ok' || data.status === 'success')) {
                    await loadModulesList();
                    updateDeployModuleSelect();
                } else {
                    alert('Ошибка удаления: ' + (data.error || response.status));
                }
            } catch (e) {
                alert('Ошибка: ' + e.message);
            }
        }

        function openUploadForUpdateModules(btn) {
            const name = btn.getAttribute('data-module-name');
            const version = btn.getAttribute('data-version');
            if (!name || !version) return;
            window._modulesUpdateOld = { module_name: name, version: version };
            const sectionUpload = document.getElementById('registry-upload-section');
            const sectionServer = document.getElementById('registry-server-section');
            if (sectionUpload) sectionUpload.style.display = 'block';
            if (sectionServer) sectionServer.style.display = 'none';
            const btnUpload = document.getElementById('registry-btn-upload-modules');
            if (btnUpload) btnUpload.setAttribute('aria-expanded', 'true');
            const btnServer = document.getElementById('registry-btn-server-modules');
            if (btnServer) btnServer.setAttribute('aria-expanded', 'false');
            const nameInput = document.getElementById('upload-module-name-modules');
            const versionInput = document.getElementById('upload-version-modules');
            if (nameInput) { nameInput.value = name; nameInput.readOnly = true; }
            if (versionInput) { versionInput.value = ''; versionInput.placeholder = `Новая версия (старую оставим как ${version})`; versionInput.readOnly = false; }
            versionInput?.focus();
        }

        function clearUploadUpdateStateModules() {
            window._modulesUpdateOld = null;
            const nameInput = document.getElementById('upload-module-name-modules');
            const versionInput = document.getElementById('upload-version-modules');
            if (nameInput) { nameInput.readOnly = false; nameInput.placeholder = '?? manifest'; }
            if (versionInput) { versionInput.placeholder = '?? manifest'; }
        }

        function showInstallDialogModules(btn) {
            const moduleName = btn.getAttribute('data-module-name');
            const version = btn.getAttribute('data-version');
            if (!moduleName || !version) return;
            const moduleSelect = document.getElementById('deploy-module-modules');
            const massSelect = document.getElementById('mass-deploy-module-modules');
            if (moduleSelect) moduleSelect.value = `${moduleName}:${version}`;
            if (massSelect) massSelect.value = `${moduleName}:${version}`;
            const deviceSelect = document.getElementById('deploy-device-modules');
            if (!deviceSelect || !deviceSelect.value) {
                alert('Выберите устройство в правом блоке, чтобы установить ' + moduleName + ' ' + version);
                if (deviceSelect) deviceSelect.focus();
            } else {
                document.getElementById('deploy-form-modules').dispatchEvent(new Event('submit'));
            }
        }

        let toolsetDataCacheModules = null;

        async function loadDeviceDetailsModules(deviceId) {
            const container = document.getElementById('device-details-content-modules');
            const desiredDiff = document.getElementById('desired-diff-modules');
            container.innerHTML = '<div class="loading">Загрузка данных устройства...</div>';
            if (desiredDiff) desiredDiff.innerHTML = '<div class="loading">Loading desired state...</div>';

            try {
                const headers = getAuthHeaders();
                const [modulesRes, toolsetRes, debugRes, desiredRes] = await Promise.all([
                    fetch(`/api/devices/${deviceId}/modules`, { headers }),
                    fetch(`/api/devices/${deviceId}/toolset`, { headers }),
                    fetch(`/api/devices/${deviceId}/modules/debug`, { headers }).catch(() => null),
                    fetch(`/api/devices/${deviceId}/modules/desired_diff`, { headers }).catch(() => null)
                ]);

                const modulesData = await modulesRes.json();
                toolsetDataCacheModules = await toolsetRes.json();
                const debugData = debugRes ? await debugRes.json() : null;
                const desiredData = desiredRes ? await desiredRes.json() : null;

                if (modulesData.status === 'ok' && toolsetDataCacheModules.status === 'ok') {
                    renderDeviceDetailsModules(deviceId, modulesData, toolsetDataCacheModules, debugData, desiredData);
                    checkPreflightModules();
                } else {
                    container.innerHTML = '<div class="error-message">Не удалось загрузить данные устройства</div>';
                }
            } catch (error) {
                container.innerHTML = `<div class="error-message">Ошибка: ${escapeHtml(error.message)}</div>`;
            }
        }

        function renderDeviceDetailsModules(deviceId, modulesData, toolsetData, debugData, desiredData) {
            const container = document.getElementById('device-details-content-modules');
            const desiredDiff = document.getElementById('desired-diff-modules');
            const modules = modulesData.modules || [];
            const toolsByModule = toolsetData.tools_by_module || {};
            const modulesWithDrift = modules.map(m => {
                const hasTools = toolsByModule[m.module_name] && toolsByModule[m.module_name].length > 0;
                let driftStatus = null;
                if (m.active && !hasTools) driftStatus = 'active_no_tools';
                else if (!m.active && hasTools) driftStatus = 'tools_no_active';
                else if (m.active && hasTools) driftStatus = 'ok';
                return { ...m, driftStatus, toolsCount: hasTools ? toolsByModule[m.module_name].length : 0 };
            });
            const recentOps = (debugData && debugData.recent_operations) ? debugData.recent_operations : [];
            const mismatches = (debugData && debugData.mismatches) ? debugData.mismatches : [];

            container.innerHTML = `
                <div class="section">
                    <h3>Снимок toolset</h3>
                    <div class="toolset-info">
                        <div class="info-card"><label>Toolset hash</label><value>${toolsetData.toolset_hash || '?'}</value></div>
                        <div class="info-card"><label>Инструментов</label><value>${toolsetData.tool_count || 0}</value></div>
                        <div class="info-card"><label>Снимок</label><value>${toolsetData.captured_at ? new Date(toolsetData.captured_at).toLocaleString() : '?'}</value></div>
                    </div>
                    <button class="btn btn-secondary" onclick="syncModulesModules('${deviceId}')">Синхронизировать снимок</button>
                </div>
                <div class="section">
                    <h3>Модули на устройстве (${modules.length})</h3>
                    ${renderModulesTableModules(modulesWithDrift, deviceId)}
                </div>
                <div class="section">
                    <h3>Последние операции</h3>
                    ${renderOperationsTableModules(recentOps)}
                </div>
                <div class="section">
                    <h3>Debug mismatch</h3>
                    ${renderMismatchesModules(mismatches)}
                </div>
                <div class="section">
                    <h3>Инструменты по модулям</h3>
                    ${renderToolsByModuleModules(toolsByModule)}
                </div>
            `;
            if (desiredDiff) desiredDiff.innerHTML = renderDesiredDiffModules(desiredData);
        }

        function renderDesiredDiffModules(desiredData) {
            if (!desiredData || desiredData.status !== 'ok') {
                return '<div class="empty">No desired diff data</div>';
            }
            const diff = desiredData.diff || [];
            if (!diff.length) return '<div class="empty">Desired state is empty</div>';
            return `
                <table>
                    <thead><tr><th>Module</th><th>Desired</th><th>Actual</th><th>Status</th><th>Reason</th></tr></thead>
                    <tbody>
                        ${diff.map(item => `<tr>
                            <td><strong>${escapeHtml(item.module_name)}</strong></td>
                            <td>${escapeHtml(item.desired_state || '?')} ${escapeHtml(item.desired_version || '')}</td>
                            <td>${escapeHtml(item.actual_state || '?')} ${escapeHtml(item.actual_version || '')}</td>
                            <td>${escapeHtml(item.diff_status || 'unknown')}</td>
                            <td>${escapeHtml(item.reason || '?')}</td>
                        </tr>`).join('')}
                    </tbody>
                </table>
            `;
        }

        function renderModulesTableModules(modules, deviceId) {
            if (!modules || modules.length === 0) return '<div class="empty">Нет установленных модулей</div>';
            return `
                <table>
                    <thead>
                        <tr>
                            <th>Модуль</th>
                            <th>Версия</th>
                            <th>State</th>
                            <th>Installed / Active</th>
                            <th>Drift</th>
                            <th>Source</th>
                            <th>Manifest</th>
                            <th>Error</th>
                            <th>Действия</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${modules.map(m => {
                            const stateClass = (m.state === 'active') ? 'active' : (m.state === 'missing') ? 'missing' : (m.state === 'removed') ? 'removed' : (m.state === 'failed') ? 'failed' : 'installed';
                            let driftHtml = '';
                            if (m.driftStatus === 'ok') driftHtml = '<span class="drift-indicator drift-ok">ok</span>';
                            else if (m.driftStatus === 'active_no_tools') driftHtml = '<span class="drift-indicator drift-warning" title="Модуль активен, но tools не попали в snapshot">warn</span>';
                            else if (m.driftStatus === 'tools_no_active') driftHtml = '<span class="drift-indicator drift-warning" title="В snapshot есть tools, но модуль не активен">warn</span>';
                            const errorHtml = m.last_error_code ? `<div class="error-text" title="${escapeHtml(m.last_error_message || '')}">${escapeHtml(m.last_error_code)}</div>` : '?';
                            const activeVersion = modules.find(x => x.module_name === m.module_name && x.active)?.version;
                            const isActive = m.active && m.version === activeVersion;
                            const hasRollbackTarget = isActive && modules.some(x =>
                                x.module_name === m.module_name &&
                                x.installed &&
                                x.version !== m.version &&
                                x.state !== 'removed'
                            );
                            return `
                                <tr>
                                    <td><strong>${escapeHtml(m.module_name)}</strong></td>
                                    <td>${escapeHtml(m.version)}</td>
                                    <td><span class="badge badge-${stateClass}">${escapeHtml(m.state)}</span></td>
                                    <td>${m.installed ? 'yes' : 'no'} / ${m.active ? 'yes' : 'no'}</td>
                                    <td>${driftHtml || '?'}</td>
                                    <td>${escapeHtml(m.source || 'device')}</td>
                                    <td>${m.manifest_version ? `v${escapeHtml(String(m.manifest_version))}${m.legacy_manifest ? ' legacy' : ''}` : '?'}</td>
                                    <td>${errorHtml}</td>
                                    <td>
                                        ${!isActive && m.installed ? `<button class="btn btn-small btn-success" onclick="activateModuleModules('${deviceId}', '${m.module_name}', '${m.version}')">Активировать</button>` : ''}
                                        ${hasRollbackTarget ? `<button class="btn btn-small btn-warning" onclick="rollbackModuleModules('${deviceId}', '${m.module_name}')">Откатить</button>` : ''}
                                        ${isActive ? `<button class="btn btn-small btn-secondary" onclick="deactivateModuleModules('${deviceId}', '${m.module_name}')">Деактивировать</button>` : ''}
                                        ${m.state === 'failed' ? `<button class="btn btn-small btn-warning" onclick="reinstallModuleModules('${deviceId}', '${m.module_name}', '${m.version}')">Переустановить</button>` : ''}
                                        ${!isActive && m.installed ? `<button class="btn btn-small btn-danger" onclick="removeModuleVersionModules('${deviceId}', '${m.module_name}', '${m.version}')">Удалить</button>` : ''}
                                    </td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            `;
        }

        function renderOperationsTableModules(operations) {
            if (!operations || operations.length === 0) return '<div class="empty">Нет операций</div>';
            return `
                <table class="operations-table">
                    <thead><tr><th>Operation ID</th><th>Kind</th><th>Status</th><th>Error</th></tr></thead>
                    <tbody>
                        ${operations.map(op => {
                            const statusClass = op.status === 'succeeded' ? 'active' : op.status === 'failed' ? 'failed' : 'installed';
                            const err = op.error_code || op.error_message ? (op.error_code ? op.error_code + ': ' : '') + (op.error_message || '') : '?';
                            return `<tr><td><code>${escapeHtml((op.operation_id || '').substring(0, 8))}...</code></td><td>${escapeHtml(op.kind || '?')}</td><td><span class="badge badge-${statusClass}">${escapeHtml(op.status || '?')}</span></td><td class="error-text">${escapeHtml(err)}</td></tr>`;
                        }).join('')}
                    </tbody>
                </table>
            `;
        }

        function renderMismatchesModules(mismatches) {
            if (!mismatches || mismatches.length === 0) return '<div class="empty">No mismatches</div>';
            return `
                <table>
                    <thead><tr><th>Module</th><th>Kind</th><th>Desired</th><th>Actual</th></tr></thead>
                    <tbody>
                        ${mismatches.map(item => `<tr><td>${escapeHtml(item.module_name || '?')}</td><td>${escapeHtml(item.kind || '?')}</td><td>${escapeHtml(item.desired_version || '?')}</td><td>${escapeHtml(item.actual_version || '?')}</td></tr>`).join('')}
                    </tbody>
                </table>
            `;
        }

        function renderToolsByModuleModules(toolsByModule) {
            if (!toolsByModule || Object.keys(toolsByModule).length === 0) return '<div class="empty">Нет инструментов</div>';
            return Object.entries(toolsByModule).map(([name, tools]) => `
                <div style="margin-bottom: 15px;">
                    <h4>${escapeHtml(name)} (${tools.length})</h4>
                    <table><thead><tr><th>Инструмент</th><th>Origin</th><th>Описание</th></tr></thead>
                    <tbody>${(tools || []).map(t => `<tr><td><code>${escapeHtml(t.name || t.tool || t.tool_id || '?')}</code></td><td>${escapeHtml(t.origin || '?')}</td><td>${escapeHtml(t.description || '?')}</td></tr>`).join('')}</tbody>
                    </table>
                </div>
            `).join('');
        }

        function checkPreflightModules() {
            const moduleSelect = document.getElementById('deploy-module-modules');
            const deviceId = document.getElementById('deploy-device-modules')?.value;
            const warningDiv = document.getElementById('preflight-warning-modules');
            if (!moduleSelect || !moduleSelect.value || !deviceId || !toolsetDataCacheModules) {
                if (warningDiv) warningDiv.style.display = 'none';
                return;
            }
            const [moduleName, version] = moduleSelect.value.split(':');
            fetch(`/api/devices/${deviceId}/modules`, { headers: getAuthHeaders() })
                .then(r => r.json())
                .then(data => {
                    if (data.status !== 'ok') return;
                    const deviceModules = data.modules || [];
                    const existing = deviceModules.find(m => m.module_name === moduleName && m.version === version);
                    const active = deviceModules.find(m => m.module_name === moduleName && m.active);
                    let text = '';
                    if (existing && existing.installed) {
                        text = `Модуль ${moduleName} ${version} уже установлен.`;
                        if (active && active.version === version) text += ' И уже активен.';
                    }
                    if (warningDiv) {
                        warningDiv.innerHTML = text;
                        warningDiv.style.display = text ? 'block' : 'none';
                    }
                }).catch(() => {});
        }

        async function syncModulesModules(deviceId) {
            try {
                const response = await fetch(`/api/devices/${deviceId}/modules/sync`, {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({ actor_role: 'admin' })
                });
                const data = await response.json();
                if (data.status === 'accepted') {
                    alert('Синхронизация запущена.');
                    setTimeout(() => loadDeviceDetailsModules(deviceId), 2000);
                } else alert('Ошибка: ' + (data.error || 'Неизвестно'));
            } catch (e) { alert('Ошибка: ' + e.message); }
        }

        async function reconcileDeviceModules(deviceId) {
            try {
                const response = await fetch(`/api/devices/${deviceId}/modules/reconcile`, {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({})
                });
                const data = await response.json();
                if (response.ok && data.status === 'ok') {
                    alert('Reconcile started.');
                    setTimeout(() => loadDeviceDetailsModules(deviceId), 1500);
                } else {
                    alert('Ошибка reconcile: ' + (data.error || 'Неизвестно'));
                }
            } catch (e) {
                alert('Ошибка reconcile: ' + e.message);
            }
        }

        function scheduleModuleDetailsRefresh(deviceId, firstDelay = 1500, secondDelay = 4000) {
            if (!deviceId) return;
            setTimeout(() => loadDeviceDetailsModules(deviceId), firstDelay);
            setTimeout(() => loadDeviceDetailsModules(deviceId), secondDelay);
        }

        async function removeModuleVersionModules(deviceId, moduleName, version) {
            if (!confirm(`Удалить модуль ${moduleName} версии ${version}?`)) return;
            try {
                const response = await fetch(`/api/devices/${deviceId}/modules/remove_version`, {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({ module_name: moduleName, version: version, actor_role: 'admin' })
                });
                const data = await response.json();
                if (data.status === 'accepted') { alert('Удаление запущено.'); scheduleModuleDetailsRefresh(deviceId); }
                else alert('Ошибка: ' + (data.error || 'Неизвестно'));
            } catch (e) { alert('Ошибка: ' + e.message); }
        }

        async function reinstallModuleModules(deviceId, moduleName, version) {
            if (!confirm(`Переустановить ${moduleName} ${version}? Будет выполнено удаление и повторная установка.`)) return;
            try {
                const modRes = await fetch(`/api/devices/${deviceId}/modules`, { headers: getAuthHeaders() });
                const modData = await modRes.json();
                const activeMod = modData.modules?.find(m => m.module_name === moduleName && m.active);
                if (activeMod) {
                    await deactivateModuleModules(deviceId, moduleName);
                    await new Promise(r => setTimeout(r, 1000));
                }
                const existing = modData.modules?.find(m => m.module_name === moduleName && m.version === version && m.installed);
                if (existing) {
                    await removeModuleVersionModules(deviceId, moduleName, version);
                    await new Promise(r => setTimeout(r, 1000));
                }
                const response = await fetch(`/api/devices/${deviceId}/modules/install`, {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({ module_name: moduleName, version: version, actor_role: 'admin' })
                });
                const data = await response.json();
                if ((response.status === 202 && data.status === 'accepted') || (response.ok && data.status === 'ok')) {
                    alert('Переустановка запущена.');
                    setTimeout(() => loadDeviceDetailsModules(deviceId), 2000);
                } else alert('Ошибка: ' + (data.error || 'Неизвестно'));
            } catch (e) { alert('Ошибка: ' + e.message); }
        }

        function updateDeployModuleSelect() {
            const select = document.getElementById('deploy-module-modules');
            const massSelect = document.getElementById('mass-deploy-module-modules');
            const opts = '<option value="">Выберите модуль...</option>' + (modulesDataTab || []).map(m =>
                `<option value="${m.module_name}:${m.version}">${m.module_name} (${m.version})</option>`
            ).join('');
            if (select) { select.innerHTML = opts; }
            if (massSelect) { massSelect.innerHTML = opts; }
        }

        function formatBytes(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        }

        // Create module form handler (POST /api/modules/create)
        document.getElementById('create-module-form-modules')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('create-module-btn-modules');
            const msg = document.getElementById('create-module-message-modules');
            btn.disabled = true;
            msg.innerHTML = '<div class="loading">Сборка и проверка...</div>';
            try {
                const payload = {
                    module_name: document.getElementById('create-module-name-modules').value.trim(),
                    version: document.getElementById('create-version-modules').value.trim(),
                    tool_name: document.getElementById('create-tool-name-modules').value.trim(),
                    method_name: document.getElementById('create-method-name-modules')?.value?.trim(),
                    description: document.getElementById('create-description-modules').value.trim(),
                    user_function_body: document.getElementById('create-code-body-modules').value.trim(),
                    risk_level: document.getElementById('create-risk-level-modules').value,
                    overwrite: document.getElementById('create-overwrite-modules').checked
                };

                const jsonFields = [
                    ['params_schema', 'create-params-schema-modules'],
                    ['platforms', 'create-platforms-modules'],
                    ['presets', 'create-presets-modules'],
                    ['capabilities', 'create-capabilities-modules'],
                    ['metadata', 'create-metadata-modules']
                ];
                for (const [payloadKey, elementId] of jsonFields) {
                    const raw = document.getElementById(elementId)?.value?.trim();
                    if (!raw) continue;
                    try {
                        payload[payloadKey] = JSON.parse(raw);
                    } catch (error) {
                        msg.innerHTML = `<div class="error-message">Ошибка JSON в ${escapeHtml(payloadKey)}: ${escapeHtml(error.message)}</div>`;
                        btn.disabled = false;
                        return;
                    }
                }

                const response = await fetch('/api/modules/create', {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                if (response.ok && data.status === 'success') {
                    msg.innerHTML = `<div class="success">Модуль создан: ${escapeHtml(data.module_name)}/${escapeHtml(data.version)}. Validation: ${escapeHtml(data.validation_status || 'passed')}.</div>`;
                    if (data.warnings && data.warnings.length) {
                        msg.innerHTML += `<div class="preflight-warning" style="display:block; margin-top:8px;">${data.warnings.map(w => escapeHtml(w)).join('<br>')}</div>`;
                    }
                    document.getElementById('create-module-form-modules').reset();
                    await loadModulesList();
                    updateDeployModuleSelect();
                } else {
                    const errList = (data.preflight_errors && data.preflight_errors.length)
                        ? '<ul>' + data.preflight_errors.map(x => '<li>' + escapeHtml(x) + '</li>').join('') + '</ul>'
                        : '';
                    msg.innerHTML = `<div class="error-message">${escapeHtml(data.error || 'Ошибка')}${errList}</div>`;
                }
            } catch (err) {
                msg.innerHTML = '<div class="error-message">Ошибка: ' + escapeHtml(err.message) + '</div>';
            } finally {
                btn.disabled = false;
            }
        });

        function escapeHtml(s) {
            if (!s) return '';
            const d = document.createElement('div');
            d.textContent = s;
            return d.innerHTML;
        }

        // Upload form handler
        document.getElementById('upload-form-modules')?.addEventListener('submit', async (e) => {
            e.preventDefault();

            const btn = document.getElementById('upload-btn-modules');
            const messageDiv = document.getElementById('upload-message-modules');
            const form = e.target;
            const formData = new FormData(form);
            const moduleNameInput = document.getElementById('upload-module-name-modules');
            const versionInput = document.getElementById('upload-version-modules');
            const overwriteCheckbox = document.getElementById('upload-overwrite-modules');
            if (overwriteCheckbox?.checked) formData.set('overwrite', 'true');

            const updateOld = window._modulesUpdateOld;
            if (updateOld) {
                const name = (moduleNameInput?.value || '').trim();
                const newVersion = (versionInput?.value || '').trim();
                if (name !== updateOld.module_name) {
                    messageDiv.innerHTML = '<div class="error">??? ?????????? ??? ?????? ?????? ????????? ? ???????.</div>';
                    return;
                }
                if (!newVersion || newVersion === updateOld.version) {
                    messageDiv.innerHTML = '<div class="error">??????? ????? ??????, ???????? ?? ??????? (' + updateOld.version + ').</div>';
                    return;
                }
            }

            btn.disabled = true;
            messageDiv.innerHTML = '<div class="loading">????????...</div>';

            try {
                const response = await fetch('/api/modules/upload', {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    body: formData
                });

                const data = await response.json();

                if (response.status === 200 && data.status === 'success') {
                    messageDiv.innerHTML = `<div class="success">?????? ????????: ${escapeHtml(data.module_name)}/${escapeHtml(data.version)}. Validation: ${escapeHtml(data.validation_status || 'passed')}.</div>`;
                    if (data.warnings && data.warnings.length) {
                        messageDiv.innerHTML += `<div class="preflight-warning" style="display:block; margin-top:8px;">${data.warnings.map(w => escapeHtml(w)).join('<br>')}</div>`;
                    }
                    if (updateOld && data.module_name === updateOld.module_name && data.version !== updateOld.version) {
                        const delRes = await fetch(`/api/modules/${encodeURIComponent(updateOld.module_name)}/${encodeURIComponent(updateOld.version)}`, {
                            method: 'DELETE',
                            headers: getAuthHeaders()
                        });
                        const delData = delRes.ok ? await delRes.json() : {};
                        if (delRes.ok && (delData.status === 'ok' || delData.status === 'success')) {
                            messageDiv.innerHTML += '<div class="success">?????? ?????? ' + escapeHtml(updateOld.version) + ' ??????? ? ???????.</div>';
                        } else {
                            messageDiv.innerHTML += '<div class="error">?????? ?????? ?? ???????: ' + escapeHtml(delData.error || String(delRes.status)) + '</div>';
                        }
                        clearUploadUpdateStateModules();
                        await loadModulesList();
                        updateDeployModuleSelect();
                    } else {
                        await loadModulesList();
                        updateDeployModuleSelect();
                    }
                    form.reset();
                    if (moduleNameInput) moduleNameInput.readOnly = false;
                    if (versionInput) versionInput.placeholder = '?? manifest';
                } else {
                    const errList = (data.preflight_errors && data.preflight_errors.length)
                        ? '<ul>' + data.preflight_errors.map(x => '<li>' + escapeHtml(x) + '</li>').join('') + '</ul>'
                        : '';
                    messageDiv.innerHTML = '<div class="error">?????? ????????: ' + escapeHtml(data.error || '??????????? ??????') + errList + '</div>';
                }
            } catch (error) {
                messageDiv.innerHTML = '<div class="error">??????: ' + escapeHtml(error.message) + '</div>';
            } finally {
                btn.disabled = false;
            }
        });

        document.getElementById('reconcile-btn-modules')?.addEventListener('click', () => {
            const deviceId = document.getElementById('deploy-device-modules')?.value || selectedDeviceIdTab;
            if (!deviceId) {
                alert('??????? ???????? ??????????.');
                return;
            }
            reconcileDeviceModules(deviceId);
        });

        // Deploy form handler
        document.getElementById('deploy-form-modules')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const deviceId = document.getElementById('deploy-device-modules').value;
            const moduleSelector = document.getElementById('deploy-module-modules').value;
            const btn = document.getElementById('deploy-btn-modules');
            
            if (!deviceId || !moduleSelector) {
                alert('Выберите устройство и модуль');
                return;
            }
            
            const [moduleName, version] = moduleSelector.split(':');
            
            btn.disabled = true;
            
            try {
                const response = await fetch(`/api/devices/${deviceId}/modules/install`, {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({
                        module_name: moduleName,
                        version: version,
                        actor_role: 'admin'
                    })
                });
                
                const data = await response.json();
                
                if (response.status === 202 && data.status === 'accepted') {
                    alert(`Установка запущена. ID операции: ${data.operation_id.substring(0, 8)}...`);
                    scheduleModuleDetailsRefresh(deviceId);
                } else {
                    alert(`Ошибка: ${data.error || 'Неизвестная ошибка'}`);
                }
            } catch (error) {
                alert(`Ошибка: ${error.message}`);
            } finally {
                btn.disabled = false;
            }
        });

        async function activateModuleModules(deviceId, moduleName, version) {
            try {
                const response = await fetch(`/api/devices/${deviceId}/modules/activate`, {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({
                        module_name: moduleName,
                        version: version,
                        actor_role: 'admin'
                    })
                });
                const data = await response.json();
                if (data.status === 'accepted') {
                    alert('Активация запущена.');
                    scheduleModuleDetailsRefresh(deviceId);
                } else {
                    alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
                }
            } catch (error) {
                alert('Ошибка: ' + error.message);
            }
        }

        async function deactivateModuleModules(deviceId, moduleName) {
            try {
                const response = await fetch(`/api/devices/${deviceId}/modules/deactivate`, {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({
                        module_name: moduleName,
                        actor_role: 'admin'
                    })
                });
                const data = await response.json();
                if (data.status === 'accepted' || data.status === 'success') {
                    alert('Деактивация запущена.');
                    scheduleModuleDetailsRefresh(deviceId);
                } else {
                    alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
                }
            } catch (error) {
                alert('Ошибка: ' + error.message);
            }
        }

        async function rollbackModuleModules(deviceId, moduleName) {
            if (!confirm(`Откатить модуль ${moduleName} на предыдущую версию?`)) return;
            try {
                const response = await fetch('/api/rollback_module', {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({
                        device_id: deviceId,
                        name: moduleName,
                        actor_role: 'admin'
                    })
                });
                const data = await response.json();
                if (data.status === 'success' || data.status === 'ok') {
                    const version = data?.data?.observations?.active_version || data?.observations?.active_version || '?';
                    alert(`Откат выполнен. Активна версия ${version}.`);
                    scheduleModuleDetailsRefresh(deviceId, 1000, 3000);
                } else {
                    alert('Ошибка rollback: ' + (data.error || 'Неизвестная ошибка'));
                }
            } catch (error) {
                alert('Ошибка rollback: ' + error.message);
            }
        }

        document.getElementById('mass-install-btn-modules')?.addEventListener('click', async () => {
            const checkboxes = document.querySelectorAll('#devices-table-modules-body .modules-device-cb:checked, #devices-checkboxes-modules input[type="checkbox"]:checked');
            const deviceIds = Array.from(checkboxes).map(cb => cb.value || cb.getAttribute('data-device-id')).filter(Boolean);
            const massSelect = document.getElementById('mass-deploy-module-modules');
            const sel = massSelect?.value;
            const replaceCb = document.getElementById('mass-deploy-replace-modules');
            const replaceIfExists = replaceCb ? replaceCb.checked : false;
            if (!sel || deviceIds.length === 0) {
                alert('Выберите хотя бы одно устройство и модуль.');
                return;
            }
            const [moduleName, version] = sel.split(':');
            if (!moduleName || !version) {
                alert('Выберите модуль (имя и версия).');
                return;
            }
            const btn = document.getElementById('mass-install-btn-modules');
            btn.disabled = true;
            const consoleEl = document.getElementById('modules-install-console');
            if (consoleEl) consoleEl.innerHTML = '';
            modulesInstallConsoleLog('Установка модуля ' + moduleName + ' ' + version + ' на ' + deviceIds.length + ' устройств...');
            try {
                const response = await fetch('/api/modules/bulk_install', {
                    method: 'POST',
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({
                        module_name: moduleName,
                        version: version,
                        device_ids: deviceIds,
                        replace_if_exists: replaceIfExists
                    })
                });
                const data = await responseToJson(response);
                if (response.status === 202 && data.status === 'accepted') {
                    const ops = data.operations || [];
                    const skipped = data.skipped || [];
                    modulesInstallConsoleLog('Принято: ' + ops.length + ' операций.');
                    skipped.forEach(s => modulesInstallConsoleLog('Пропущено ' + (s.device_id || '') + ': ' + (s.reason || ''), true));
                    ops.forEach(o => modulesInstallConsoleLog('Устройство ' + (o.device_id || '').slice(0, 8) + '... → операция ' + (o.operation_id || '').slice(0, 8) + '...'));
                    if (ops.length > 0) {
                        modulesInstallConsoleLog('Ожидание результатов (опрос статуса операций)...');
                        for (const o of ops) {
                            const opId = o.operation_id;
                            const devId = (o.device_id || '').slice(0, 8);
                            await new Promise(r => setTimeout(r, 1500));
                            try {
                                const opRes = await fetch('/api/operations/' + encodeURIComponent(opId), { headers: getAuthHeaders() });
                                const opData = await responseToJson(opRes);
                                const status = opData.operation?.status || opData.status || 'unknown';
                                const err = opData.operation?.error_message || opData.error_message;
                                if (status === 'succeeded') modulesInstallConsoleLog(devId + '...: успех.');
                                else if (status === 'failed' || status === 'timed_out') modulesInstallConsoleLog(devId + '...: ' + status + (err ? ' — ' + err : ''), true);
                                else modulesInstallConsoleLog(devId + '...: ' + status);
                            } catch (e) {
                                modulesInstallConsoleLog(devId + '...: ошибка запроса статуса — ' + e.message, true);
                            }
                        }
                        modulesInstallConsoleLog('Готово.');
                    }
                    if (selectedDeviceIdTab) scheduleModuleDetailsRefresh(selectedDeviceIdTab);
                } else {
                    modulesInstallConsoleLog('Ошибка: ' + (data.error || 'Неизвестно'), true);
                    if (data.error_code) modulesInstallConsoleLog('Код: ' + data.error_code, true);
                }
            } catch (e) {
                modulesInstallConsoleLog('Ошибка: ' + e.message, true);
            } finally {
                btn.disabled = false;
            }
        });

        document.getElementById('deploy-module-modules')?.addEventListener('change', checkPreflightModules);
        document.getElementById('deploy-device-modules')?.addEventListener('change', function() {
            const deviceId = this.value;
            if (deviceId) selectDeviceModules(deviceId);
            else document.getElementById('device-details-modules').style.display = 'none';
            checkPreflightModules();
        });

        const AUTH_TOKEN_KEY = 'admin_auth_token';
        const USER_LOGIN_KEY = 'admin_user_login';

        function cancelQueueReconnectTimer() {
            if (queueReconnectTimer) {
                clearTimeout(queueReconnectTimer);
                queueReconnectTimer = null;
            }
        }

        function closeQueueWs() {
            cancelQueueReconnectTimer();
            if (queueWs) {
                const ws = queueWs;
                queueWs = null;
                try {
                    ws.onclose = null;
                    ws.onerror = null;
                    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
                        ws.close();
                    }
                } catch (e) {
                    console.warn('queue ws close', e);
                }
            }
            queueState.subscribedTicketIds.clear();
            queueSetRealtimeIndicator(false);
        }

        function resetAuthSessionState() {
            authSessionInvalid = false;
            cancelQueueReconnectTimer();
        }

        function handleAuthFailure(message) {
            if (authSessionInvalid) {
                return;
            }
            authSessionInvalid = true;
            localStorage.removeItem(AUTH_TOKEN_KEY);
            localStorage.removeItem(USER_LOGIN_KEY);
            localStorage.removeItem('admin_actor_role');
            if (typeof stopPolling === 'function') {
                stopPolling();
            }
            if (typeof queueStopPolling === 'function') {
                queueStopPolling();
            }
            if (queueDebounceReloadTimer) {
                clearTimeout(queueDebounceReloadTimer);
                queueDebounceReloadTimer = null;
            }
            appInitialized = false;
            closeQueueWs();
            showLogin();
            const errorDiv = document.getElementById('loginError');
            if (errorDiv) {
                errorDiv.textContent = message || 'Сессия истекла. Войдите заново.';
                errorDiv.style.display = 'block';
            }
        }
        
        // Check authentication on page load
        document.addEventListener('DOMContentLoaded', () => {
            const token = localStorage.getItem(AUTH_TOKEN_KEY);
            if (token) {
                // Verify token is still valid by making a test request
                verifyToken(token);
            } else {
                showLogin();
            }
        });
        
        // Verify token by making a test API request
        async function verifyToken(token) {
            try {
                const response = await fetch('/api/agents', {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });
                
                if (response.ok || response.status === 404) {
                    // Token is valid (404 is ok for empty agents list)
                    resetAuthSessionState();
                    showMainContent(token);
                    // Initialize app if not already initialized
                    if (typeof initializeApp === 'function') {
                        initializeApp();
                    }
                } else if (response.status === 401) {
                    handleAuthFailure('Сессия панели истекла. Войдите заново.');
                } else {
                    showLogin();
                }
            } catch (error) {
                console.error('Token verification error:', error);
                showLogin();
            }
        }
        
        // Show login form, hide main content
        function showLogin() {
            document.getElementById('loginContainer').style.display = 'flex';
            document.getElementById('mainContent').style.display = 'none';
        }
        
        // Show main content, hide login
        function showMainContent(token) {
            document.getElementById('loginContainer').style.display = 'none';
            document.getElementById('mainContent').style.display = 'block';
            // Ticket Queue is default tab: init if visible
            const queueTab = document.getElementById('tab-queue');
            if (queueTab && queueTab.classList.contains('active')) {
                const b = document.getElementById('queueTableBody');
                if (b && !b.dataset.inited && typeof queueInit === 'function') {
                    b.dataset.inited = '1';
                    queueInit();
                }
            }
            // Update user info in header if available
            const userLogin = localStorage.getItem(USER_LOGIN_KEY);
            if (userLogin) {
                updateUserInfo(userLogin);
            }
        }
        
        // Update user info in header
        function updateUserInfo(login) {
            const headerActions = document.querySelector('.header-actions');
            if (headerActions && !document.getElementById('userInfo')) {
                const userInfo = document.createElement('div');
                userInfo.className = 'user-info';
                userInfo.id = 'userInfo';
                userInfo.innerHTML = `
                    <span>👤 ${login}</span>
                    <button class="btn btn-secondary" onclick="handleLogout()" style="padding: 6px 12px; font-size: 12px;">Logout</button>
                `;
                headerActions.appendChild(userInfo);
            }
        }
        
        // Handle login form submission
        async function handleLogin(event) {
            event.preventDefault();
            
            const login = document.getElementById('loginInput').value;
            const password = document.getElementById('passwordInput').value;
            const errorDiv = document.getElementById('loginError');
            
            errorDiv.style.display = 'none';
            
            try {
                const response = await fetch('/api/ui_login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        login: login,
                        password: password
                    })
                });
                
                const data = await response.json();
                
                if (response.ok && data.status === 'success') {
                    // Save token and user info
                    localStorage.setItem(AUTH_TOKEN_KEY, data.token);
                    localStorage.setItem(USER_LOGIN_KEY, data.user_login);
                    if (data.actor_role) localStorage.setItem('admin_actor_role', data.actor_role);
                    resetAuthSessionState();
                    
                    // Show main content
                    showMainContent(data.token);
                    
                    // Initialize main app
                    if (typeof initializeApp === 'function') {
                        initializeApp();
                    }
                } else {
                    errorDiv.textContent = data.error || 'Ошибка входа';
                    errorDiv.style.display = 'block';
                }
            } catch (error) {
                errorDiv.textContent = `Ошибка: ${error.message}`;
                errorDiv.style.display = 'block';
            }
        }
        
        // Handle logout
        function handleLogout() {
            resetAuthSessionState();
            localStorage.removeItem(AUTH_TOKEN_KEY);
            localStorage.removeItem(USER_LOGIN_KEY);
            localStorage.removeItem('admin_actor_role');
            if (typeof stopPolling === 'function') {
                stopPolling();
            }
            if (typeof queueStopPolling === 'function') {
                queueStopPolling();
            }
            closeQueueWs();
            appInitialized = false;
            showLogin();
        }
        
        // Intercept all fetch calls to add auth token
        const originalFetch = window.fetch;
        window.fetch = function(...args) {
            const token = localStorage.getItem(AUTH_TOKEN_KEY);
            
            if (token && args[0] && typeof args[0] === 'string') {
                // Simple URL fetch
                if (!args[1]) {
                    args[1] = {};
                }
                if (!args[1].headers) {
                    args[1].headers = {};
                }
                if (!args[1].headers['Authorization']) {
                    args[1].headers['Authorization'] = `Bearer ${token}`;
                }
            } else if (token && args[0] && typeof args[0] === 'object') {
                // Request object fetch
                if (!args[0].headers) {
                    args[0].headers = {};
                }
                if (!args[0].headers['Authorization']) {
                    args[0].headers['Authorization'] = `Bearer ${token}`;
                }
            }
            
            const requestUrl = typeof args[0] === 'string'
                ? args[0]
                : (args[0] && typeof args[0].url === 'string' ? args[0].url : '');
            
            return originalFetch.apply(this, args).then((response) => {
                if (
                    response
                    && response.status === 401
                    && token
                    && !authSessionInvalid
                    && requestUrl
                    && requestUrl.indexOf('/api/') !== -1
                    && requestUrl.indexOf('/api/ui_login') === -1
                    && requestUrl.indexOf('/api/login') === -1
                ) {
                    handleAuthFailure('Сессия панели истекла. Войдите заново.');
                }
                return response;
            });
        };
