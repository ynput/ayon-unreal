from abc import ABC
import unreal


from abc import ABC, abstractmethod
import unreal


class UnrealBackend(ABC):
    @staticmethod
    @abstractmethod
    def install():
        pass

    @staticmethod
    @abstractmethod
    def ls() -> list:
        pass

    @staticmethod
    @abstractmethod
    def ls_inst():
        pass

    @staticmethod
    @abstractmethod
    def containerise(name, namespace, nodes, context, loader=None, suffix="_CON"):
        pass

    @staticmethod
    @abstractmethod
    def imprint(node, data):
        pass

    @staticmethod
    @abstractmethod
    def create_container(container: str, path: str) -> unreal.Object:
        pass

    @staticmethod
    @abstractmethod
    def create_publish_instance(instance: str, path: str) -> unreal.Object:
        pass
