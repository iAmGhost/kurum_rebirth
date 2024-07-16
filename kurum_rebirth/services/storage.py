from abc import ABCMeta, abstractproperty, abstractmethod



class Storage(metaclass=ABCMeta):
    def init(self):
        pass

    @abstractmethod
    def configure(self, gui: bool):
        pass

    @abstractmethod
    def upload(self, from_path: str, to_path: str):
        pass

    @abstractmethod
    def download(self, from_path: str, to_path: str):
        pass

    @abstractmethod
    def get_remote_last_sync(self, key: str) -> int:
        pass

    @abstractmethod
    def update_remote_last_sync(self, key: str):
        pass

    @abstractproperty
    def is_authorized(self) -> bool:
        return False
