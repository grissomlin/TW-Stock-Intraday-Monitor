# -*- coding: utf-8 -*-
from datetime import datetime

def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{ts}: {msg}", flush=True)
