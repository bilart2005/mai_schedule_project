import time
from backend.notifier.check_changes import check_new_changes
from backend.notifier.notifications_config import CHECK_INTERVAL_SECONDS

if __name__ == "__main__":
    while True:
        check_new_changes()
        time.sleep(CHECK_INTERVAL_SECONDS)
