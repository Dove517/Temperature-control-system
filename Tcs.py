from config import Tconfig
from GUI import Ttray

if __name__ == "__main__":
    Tconfig.init()
    raise SystemExit(Ttray.main())