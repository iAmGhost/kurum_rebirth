import logging
import webbrowser

import pendulum

import PySimpleGUI as sg

from dropbox import DropboxOAuth2FlowNoRedirect, Dropbox
from dropbox.exceptions import ApiError
from dropbox.files import GetMetadataError, FileMetadata, WriteMode

from kurum_rebirth.services.storage import Storage
from kurum_rebirth.config import get_config, save_config
from kurum_rebirth.error import KurumError
from kurum_rebirth.vendor import DROPBOX_APP_KEY


logger = logging.getLogger(__name__)


class DropboxStorage(Storage):
    def init(self):
        config = get_config()

        if config.dropbox.refresh_token:
            self.dropbox = Dropbox(
                app_key=DROPBOX_APP_KEY,
                oauth2_refresh_token=config.dropbox.refresh_token,
            )

            self.dropbox.check_and_refresh_access_token()

    def configure(self, gui: bool):
        config = get_config()

        auth_flow = DropboxOAuth2FlowNoRedirect(DROPBOX_APP_KEY, use_pkce=True, token_access_type='offline')

        layout = [
            [sg.Text("Step 1. Login with Dropbox"), sg.Button('Login', key='-LOGIN-')],
            [sg.Input(key="auth_url", disabled=True)],
            [sg.Text("Step 2. Copy access code to below.")],
            [sg.Input(key="access_code", disabled=True)],
            [sg.Button("Submit", key="-SUBMIT-", disabled=True)],
        ]
        window = sg.Window("Dropbox Login", layout, modal=True, finalize=True, icon="data/assets/Kurum_512px.ico")
        window.bring_to_front()

        while True:
            event, values = window.read()

            match event:
                case '-LOGIN-':
                    authorize_url = auth_flow.start()
                    webbrowser.open(authorize_url)
                    window['auth_url'].update(value=authorize_url)
                    window['-SUBMIT-'].update(disabled=False)
                    window['access_code'].update(disabled=False)

                case '-SUBMIT-':
                    oauth_result = auth_flow.finish(values['access_code'])

                    config.dropbox.refresh_token = oauth_result.refresh_token
                    config.active_storage = 'dropbox'

                    save_config()

                    self.dropbox = Dropbox(
                        app_key=DROPBOX_APP_KEY,
                        oauth2_access_token=oauth_result.access_token,
                        oauth2_refresh_token=oauth_result.refresh_token,
                        oauth2_access_token_expiration=oauth_result.expires_at,
                    )

                    logger.info("Saved Dropbox Login!")

                    break

                case sg.WIN_CLOSED:
                    break

        window.close()

    def upload(self, str_path: str, to_path: str):
        with open(str_path, 'rb') as f:
            self.dropbox.files_upload(f.read(), to_path, mode=WriteMode.overwrite)

    def download(self, from_path: str, to_path: str):
        self.dropbox.files_download_to_file(to_path, from_path)

    def get_remote_last_sync(self, key: str) -> int:
        try:
            meta: FileMetadata = self.dropbox.files_get_metadata(f'/backups/{key}/last_sync')
            return pendulum.instance(meta.server_modified).int_timestamp
        except ApiError as e:
            if isinstance(e.error, GetMetadataError):
                return -1

            raise KurumError

    def update_remote_last_sync(self, key: str):
        self.dropbox.files_upload("".encode(), f"/backups/{key}/last_sync", mode=WriteMode.overwrite)

    @property
    def is_authorized(self) -> bool:
        config = get_config()
        return bool(config.dropbox.refresh_token)
