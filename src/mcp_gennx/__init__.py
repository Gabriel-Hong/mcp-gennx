from .server import create_server


def main():
    server = create_server()
    server.run(transport="stdio")
