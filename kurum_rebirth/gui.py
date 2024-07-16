import platform
import time
import logging

import PySimpleGUI as sg
from psgtray import SystemTray
from pydantic import BaseModel

from kurum_rebirth.logging import init_logging
from kurum_rebirth.services.dropbox_storage import DropboxStorage
from kurum_rebirth.services.windows_sync import WindowsSyncService
from kurum_rebirth.services.sync import SyncService, SyncServiceHandler
from kurum_rebirth.config import load_config
from kurum_rebirth.const import POLL_INTERVAL_SECONDS
from kurum_rebirth.schema import InitTask, SyncConfig

from kurum_rebirth import VERSION


logger = logging.getLogger(__name__)


def get_sync_service_class():
    match platform.system():
        case 'Windows':
            return WindowsSyncService



def main():
    menu = ['', ['Show Window', 'Exit']]
    tooltip = 'Tooltip'

    configure_storage_button = sg.Button('Configure Storage', key='-CONFIG_STORAGE-')

    layout = [[sg.Multiline(size=(60,10), reroute_stdout=False, reroute_cprint=True, write_only=True, key='-OUT-')],
              [configure_storage_button, sg.Button('Hide Window'), sg.Button('Exit')]]

    window = sg.Window(f'KurumRebirth (v{VERSION})', layout, finalize=True, enable_close_attempted_event=True,
                       icon="assets/Kurum_512px.ico")
    window.hide()

    init_logging()

    load_config()

    storage = DropboxStorage()
    storage.init()

    service_handler = GUISyncServiceHandler(window)

    sync_service = get_sync_service_class()(storage=storage, service_handler=service_handler)
    sync_service.scan_config()

    running = True

    if not storage.is_authorized:
        window.un_hide()
        logger.error("Storage not configured!!")

    def poll_sync_service():
        while running:
            sync_service.poll()
            time.sleep(POLL_INTERVAL_SECONDS)

    window.start_thread(poll_sync_service, ('-SYNC_SERVICE_START-', '-SYNC_SERVICE_END-'))

    tray = SystemTray(menu, single_click_events=False, window=window, tooltip=tooltip, icon="assets/Kurum_512px.png")
    tray.show_icon()

    while True:
        event, values = window.read()

        if event == tray.key:
            event = values[event]

        match event:
            case sg.WIN_CLOSED | 'Exit':
                break

            case '-FOLDER_PICKER-':
                config: SyncConfig
                task: InitTask
                config, task = values['-FOLDER_PICKER-']
                selected_path = sg.PopupGetFolder(task.description, title=config.name)

                if selected_path:
                    config.set_user_setting(task.name, selected_path)
                    config.disabled = False

            case '-CONFIG_STORAGE-':
                storage.configure(gui=True)

            case '-SHOW_NOTIFICATION-':
                notification: Notification = values['-SHOW_NOTIFICATION-']
                tray.show_message(title=notification.title, message=notification.message)

            case 'Show Window' | sg.EVENT_SYSTEM_TRAY_ICON_DOUBLE_CLICKED:
                window.un_hide()
                window.bring_to_front()

            case 'Hide Window' | sg.WIN_CLOSE_ATTEMPTED_EVENT:
                window.hide()


    running = False

    tray.close()
    window.close()


class GUISyncServiceHandler(SyncServiceHandler):
    def __init__(self, window: sg.Window):
        self.window = window

    def on_init_task(self, config: SyncConfig, task: InitTask):
        self.window.write_event_value('-FOLDER_PICKER-', (config, task))

    def on_backup_start(self, config: SyncConfig):
        self.window.write_event_value('-SHOW_NOTIFICATION-', Notification(title="KurumRebirth", message=f"Backup start: {config.name}"))

    def on_backup_end(self, config: SyncConfig):
        self.window.write_event_value('-SHOW_NOTIFICATION-', Notification(title="KurumRebirth", message=f"Backup finished: {config.name}"))

    def on_restore_start(self, config: SyncConfig):
        self.window.write_event_value('-SHOW_NOTIFICATION-', Notification(title="KurumRebirth", message=f"Restore start: {config.name}"))

    def on_restore_end(self, config: SyncConfig):
        self.window.write_event_value('-SHOW_NOTIFICATION-', Notification(title="KurumRebirth", message=f"Restore finished: {config.name}"))


class Notification(BaseModel):
    title: str | None = None
    message: str | None = None


if __name__ == '__main__':
    main()