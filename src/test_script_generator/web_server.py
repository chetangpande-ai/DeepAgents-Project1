import uvicorn


def main() -> None:
    uvicorn.run("test_script_generator.web_api:app", host="127.0.0.1", port=8001)
