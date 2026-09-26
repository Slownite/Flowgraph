from pipeline import run_pipeline


def load_config():
    return {"mode": "demo"}


def main():
    config = load_config()
    return run_pipeline(config)
