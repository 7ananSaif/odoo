declare module "services" {
    import { IotWebsocketService } from "@iot/iot_websocket_service";

    export interface Services {
        iot_websocket: typeof IotWebsocketService
    }
}
