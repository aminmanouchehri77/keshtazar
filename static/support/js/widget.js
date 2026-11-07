(function () {
    "use strict";

    const root = document.getElementById("keshtSupportChat");
    if (!root) return;

    const launcher = document.getElementById("supportChatLauncher");
    const panel = document.getElementById("supportChatPanel");
    const closeButton = document.getElementById("supportChatClose");
    const form = document.getElementById("supportChatForm");
    const input = document.getElementById("supportChatInput");
    const sendButton = document.getElementById("supportChatSend");
    const messageList = document.getElementById("supportChatMessages");
    const body = document.getElementById("supportChatBody");
    const welcome = document.getElementById("supportChatWelcome");
    const notice = document.getElementById("supportChatNotice");
    const errorBox = document.getElementById("supportChatError");
    const statusLabel = document.getElementById("supportChatStatus");
    const codeLabel = document.getElementById("supportChatCode");
    const counter = document.getElementById("supportChatCount");
    const csrfInput = form.querySelector("[name='csrfmiddlewaretoken']");
    const knownMessages = new Map();
    const persianDigits = "۰۱۲۳۴۵۶۷۸۹";
    let lastMessageId = 0;
    let connected = false;
    let initialized = false;
    let loading = false;
    let sending = false;
    let pollTimer = null;
    let reconnectTimer = null;
    let socket = null;
    let websocketEnabled = false;
    const DEBUG_STORAGE_KEY = "keshtSupportChatDebug";
    let debugEnabled = false;

    try {
        debugEnabled = new URLSearchParams(window.location.search).get("support_chat_debug") === "1"
            || window.localStorage.getItem(DEBUG_STORAGE_KEY) === "1";
    } catch (error) {}

    function debugLog(eventName, details) {
        if (!debugEnabled || !window.console || typeof window.console.info !== "function") return;
        window.console.info("[KeshtSupportChat]", Object.assign({
            event: eventName,
            timestamp: new Date().toISOString()
        }, details || {}));
    }

    function errorDetails(error) {
        return {
            http_status: Number.isFinite(error && error.status) ? error.status : null,
            error_type: error && error.name ? String(error.name) : "Error"
        };
    }

    window.keshtSupportChatDebug = function (enabled) {
        debugEnabled = enabled !== false;
        try {
            if (debugEnabled) window.localStorage.setItem(DEBUG_STORAGE_KEY, "1");
            else window.localStorage.removeItem(DEBUG_STORAGE_KEY);
        } catch (error) {}
        window.console.info("[KeshtSupportChat] Debug logging " + (debugEnabled ? "enabled" : "disabled")
            + ". Message content and identifiers are omitted.");
    };

    if (debugEnabled) debugLog("debug_enabled", { source: "query_or_local_storage" });

    function toPersianDigits(value) {
        return String(value).replace(/\d/g, function (digit) {
            return persianDigits[Number(digit)];
        });
    }

    function messageTime(value) {
        if (!value) return "";
        let normalized = String(value);
        if (!/(Z|[+-]\d{2}:?\d{2})$/i.test(normalized)) normalized += "+03:30";
        const date = new Date(normalized);
        if (Number.isNaN(date.getTime())) return "";
        return new Intl.DateTimeFormat("fa-IR", {
            hour: "2-digit",
            minute: "2-digit",
            timeZone: "Asia/Tehran"
        }).format(date);
    }

    function updateComposer() {
        const hasText = Boolean(input.value.trim());
        input.disabled = !connected || sending;
        sendButton.disabled = !connected || sending || !hasText;
        root.querySelectorAll("[data-prompt]").forEach(function (prompt) {
            prompt.disabled = !connected || sending;
        });
        counter.textContent = toPersianDigits(input.value.length) + " / ۳۰۰۰";
        input.style.height = "auto";
        input.style.height = Math.min(input.scrollHeight, 112) + "px";
    }

    function updateMessage(message, advanceCursor) {
        if (!message || message.id === undefined || message.id === null) return;
        const id = String(message.id);
        const numericId = Number(message.id);
        if (advanceCursor && Number.isSafeInteger(numericId)) lastMessageId = Math.max(lastMessageId, numericId);

        let item = knownMessages.get(id);
        if (!item) {
            item = document.createElement("li");
            item.className = "support-chat__message " +
                (message.sender === "visitor" ? "support-chat__message--visitor" : "support-chat__message--support");

            const bubble = document.createElement("span");
            bubble.className = "support-chat__bubble";
            bubble.textContent = String(message.body || "");

            const meta = document.createElement("span");
            meta.className = "support-chat__message-meta";
            const time = document.createElement("time");
            time.dateTime = String(message.created_at || "");
            time.textContent = messageTime(message.created_at);
            meta.appendChild(time);

            const delivery = document.createElement("span");
            delivery.className = "support-chat__delivery";
            meta.appendChild(delivery);
            item.append(bubble, meta);
            item._deliveryLabel = delivery;
            item._messageId = numericId;
            const nextItem = Array.from(messageList.children).find(function (child) {
                return Number.isSafeInteger(numericId) && child._messageId > numericId;
            });
            messageList.insertBefore(item, nextItem || null);
            knownMessages.set(id, item);
        }

        const deliveryLabel = item._deliveryLabel;
        if (message.sender === "visitor" && deliveryLabel) {
            deliveryLabel.className = "support-chat__delivery";
            if (message.delivery_status === "failed") {
                deliveryLabel.textContent = "ارسال به پشتیبانی ناموفق بود؛ لطفاً تلفنی پیگیری کنید.";
                deliveryLabel.classList.add("support-chat__delivery--failed");
            } else if (message.delivery_status === "pending") {
                deliveryLabel.textContent = "در حال ارسال به پشتیبانی…";
            } else if (message.delivery_status === "sent") {
                deliveryLabel.textContent = "ارسال شد";
            } else {
                deliveryLabel.textContent = "";
            }
        }

        welcome.hidden = knownMessages.size > 0;
        body.scrollTop = body.scrollHeight;
    }

    function showError(message) {
        errorBox.textContent = message || "ارتباط برقرار نشد. اتصال اینترنت را بررسی کنید.";
        errorBox.hidden = false;
    }

    async function readJson(response) {
        try {
            return await response.json();
        } catch (error) {
            return {};
        }
    }

    async function loadSession() {
        if (loading) return;
        loading = true;
        try {
            const response = await fetch(root.dataset.sessionUrl, {
                credentials: "same-origin",
                cache: "no-store",
                headers: { "Accept": "application/json" }
            });
            const result = await readJson(response);
            if (!response.ok) {
                const error = new Error(result.error || "گفتگو بارگذاری نشد. دوباره تلاش کنید.");
                error.status = response.status;
                throw error;
            }

            connected = Boolean(result.support_connected);
            websocketEnabled = Boolean(result.websocket_enabled);
            initialized = true;
            debugLog("session_result", {
                http_status: response.status,
                support_connected: connected,
                websocket_enabled: websocketEnabled,
                initial_message_count: Array.isArray(result.messages) ? result.messages.length : 0
            });
            statusLabel.textContent = connected ? "گفتگوی آنلاین" : "تماس با پشتیبانی";
            notice.hidden = connected;
            if (result.conversation) {
                codeLabel.textContent = "کد گفتگو: " + result.conversation;
                codeLabel.hidden = false;
            }
            (result.messages || []).forEach(function (message) { updateMessage(message, true); });
            errorBox.hidden = true;
            updateComposer();
        } catch (error) {
            connected = false;
            websocketEnabled = false;
            statusLabel.textContent = "اتصال برقرار نشد";
            notice.hidden = false;
            debugLog("session_failed", errorDetails(error));
            showError(error.message);
            updateComposer();
        } finally {
            loading = false;
        }
    }

    async function refreshMessages() {
        if (!initialized || !connected || loading) {
            if (!initialized) await loadSession();
            return;
        }
        loading = true;
        try {
            const url = new URL(root.dataset.messagesUrl, window.location.href);
            url.searchParams.set("after", String(lastMessageId));
            const response = await fetch(url.toString(), {
                credentials: "same-origin",
                cache: "no-store",
                headers: { "Accept": "application/json" }
            });
            const result = await readJson(response);
            if (!response.ok) {
                const error = new Error(result.error || "دریافت پیام‌های تازه انجام نشد.");
                error.status = response.status;
                throw error;
            }
            const messages = Array.isArray(result.messages) ? result.messages : [];
            debugLog("poll_result", {
                http_status: response.status,
                received: messages.length,
                support_replies: messages.filter(function (message) { return message.sender === "support"; }).length,
                visitor_messages: messages.filter(function (message) { return message.sender === "visitor"; }).length
            });
            messages.forEach(function (message) { updateMessage(message, true); });
            errorBox.hidden = true;
        } catch (error) {
            debugLog("poll_failed", errorDetails(error));
            showError(error.message);
        } finally {
            loading = false;
        }
    }

    function stopPolling() {
        if (pollTimer) {
            window.clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    function startPolling() {
        if (pollTimer) return;
        pollTimer = window.setInterval(function () {
            if (!panel.hidden && document.visibilityState === "visible") refreshMessages();
        }, 4500);
    }

    function scheduleReconnect() {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = window.setTimeout(function () {
            if (!panel.hidden && connected && websocketEnabled) connectWebSocket();
        }, 5000);
    }

    function connectWebSocket() {
        if (!window.WebSocket || !websocketEnabled || panel.hidden || !connected) {
            startPolling();
            return;
        }
        if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return;

        const url = new URL(root.dataset.websocketUrl, window.location.href);
        url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        url.searchParams.set("after", String(lastMessageId));
        debugLog("websocket_connecting", { secure: url.protocol === "wss:" });
        const activeSocket = new WebSocket(url.toString());
        socket = activeSocket;

        activeSocket.addEventListener("open", function () {
            if (socket !== activeSocket) return;
            debugLog("websocket_open", {});
            window.clearTimeout(reconnectTimer);
            startPolling();
            refreshMessages();
        });
        activeSocket.addEventListener("message", function (event) {
            try {
                const payload = JSON.parse(event.data);
                if (payload.type === "message") {
                    debugLog("websocket_message", {
                        sender: payload.message && payload.message.sender === "support" ? "support" : "visitor"
                    });
                    updateMessage(payload.message);
                    refreshMessages();
                }
            } catch (error) {
                debugLog("websocket_message_invalid", { error_type: error.name || "Error" });
                showError("پیام دریافتی از سرور خوانا نبود.");
            }
        });
        activeSocket.addEventListener("close", function (event) {
            if (socket !== activeSocket) return;
            debugLog("websocket_closed", { close_code: event.code });
            socket = null;
            if (!panel.hidden) {
                startPolling();
                scheduleReconnect();
            }
        });
        activeSocket.addEventListener("error", function () {
            debugLog("websocket_error", {});
            activeSocket.close();
        });
    }

    function openPanel() {
        panel.hidden = false;
        launcher.hidden = true;
        launcher.setAttribute("aria-expanded", "true");
        loadSession().then(function () {
            if (connected) {
                input.focus();
                if (websocketEnabled) connectWebSocket();
                else startPolling();
            } else {
                closeButton.focus();
            }
        });
    }

    function closePanel() {
        panel.hidden = true;
        launcher.hidden = false;
        launcher.setAttribute("aria-expanded", "false");
        stopPolling();
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
        if (socket) {
            const activeSocket = socket;
            socket = null;
            activeSocket.close();
        }
        launcher.focus();
    }

    launcher.addEventListener("click", openPanel);
    closeButton.addEventListener("click", closePanel);
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && !panel.hidden) closePanel();
    });

    input.addEventListener("input", updateComposer);
    input.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
            event.preventDefault();
            form.requestSubmit();
        }
    });

    root.addEventListener("click", function (event) {
        const prompt = event.target.closest("[data-prompt]");
        if (!prompt || !connected) return;
        input.value = prompt.dataset.prompt || "";
        updateComposer();
        input.focus();
    });

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        const text = input.value.trim();
        if (!text || !connected || sending) return;

        sending = true;
        errorBox.hidden = true;
        updateComposer();
        try {
            const response = await fetch(root.dataset.messagesUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfInput ? csrfInput.value : "",
                    "Accept": "application/json"
                },
                body: JSON.stringify({ body: text })
            });
            const result = await readJson(response);
            if (!response.ok) {
                const error = new Error(result.error || "ارسال پیام انجام نشد. دوباره تلاش کنید.");
                error.status = response.status;
                throw error;
            }
            debugLog("send_result", {
                http_status: response.status,
                delivery_status: result.message && result.message.delivery_status
            });
            updateMessage(result.message);
            input.value = "";
            errorBox.hidden = true;
        } catch (error) {
            debugLog("send_failed", errorDetails(error));
            showError(error.message);
        } finally {
            sending = false;
            updateComposer();
            if (connected) input.focus();
        }
    });

    messageList.setAttribute("aria-live", "polite");
    messageList.setAttribute("aria-relevant", "additions text");
    updateComposer();
})();
