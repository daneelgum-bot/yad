#pragma once
#include "esp_websocket_client.h"

typedef void (*websocket_cmd_handler_t)(const char *data, size_t len);

esp_websocket_client_handle_t websocket_app_get_client(void);
void websocket_app_start(void);
void websocket_set_cmd_handler(websocket_cmd_handler_t handler);