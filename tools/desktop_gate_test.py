import os
try:
    open("/Users/mac/Desktop/_gate_test.txt","w"); print("NG 書けてしまった")
except PermissionError as e: print("OK 止まった:", e)
open("/Users/mac/tamago/_gate_ok.txt","w").write("x"); print("OK 工場側は書ける")
