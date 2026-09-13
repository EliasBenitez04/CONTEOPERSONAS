from app.main import main
from app.utils.logging_setup import setup_client_logging


if __name__ == "__main__":
    log_file = setup_client_logging()
    print(f"[LOG] Archivo: {log_file}")
    main()
