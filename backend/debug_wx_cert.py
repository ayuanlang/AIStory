import logging
import os
import sys
from app.core.config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models.all_models import APISetting

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wx_debug")

# Setup DB
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

def debug_cert_download():
    print("-" * 50)
    print("Starting WeChat Pay Certificate Download Debugger")
    print("-" * 50)

    try:
        from wechatpayv3 import WeChatPay, WeChatPayType
    except ImportError:
        print("CRITICAL: wechatpayv3 not installed.")
        return

    # 1. Get Settings
    setting = db.query(APISetting).filter(
        APISetting.category == "System_Payment",
        APISetting.provider == "wechat_pay"
    ).first()

    if not setting or not setting.config:
        print("No WeChat Pay settings found in DB.")
        return

    conf = setting.config
    mchid = conf.get("mchid")
    cert_serial_no = conf.get("cert_serial_no")
    api_v3_key = setting.api_key
    private_key = conf.get("private_key")
    
    # Clean Key
    if private_key and "-----BEGIN PRIVATE KEY-----" in private_key:
        start = private_key.find("-----BEGIN PRIVATE KEY-----")
        end_marker = "-----END PRIVATE KEY-----"
        end = private_key.find(end_marker)
        if start != -1 and end != -1:
            private_key = private_key[start : end + len(end_marker)]
    
    print(f"MCHID: {mchid}")
    print(f"Serial No: {cert_serial_no}")
    print(f"API V3 Key: {api_v3_key} (Len: {len(api_v3_key) if api_v3_key else 0})")
    print(f"Private Key: {'Loaded' if private_key else 'Missing'}")

    # Check for Certificate Bundle inside Private Key
    embedded_cert = None
    if conf.get("private_key") and "-----BEGIN CERTIFICATE-----" in conf.get("private_key"):
        try:
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend
            
            raw_pem = conf.get("private_key")
            start = raw_pem.find("-----BEGIN CERTIFICATE-----")
            end = raw_pem.find("-----END CERTIFICATE-----") + len("-----END CERTIFICATE-----")
            cert_pem = raw_pem[start:end].encode('utf-8')
            
            cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
            serial_int = cert.serial_number
            serial_hex = format(serial_int, 'X')
            
            print(f"Found Embedded Certificate with Serial No: {serial_hex}")
            if serial_hex != cert_serial_no:
                 print(f"WARNING: Current Serial No {cert_serial_no} does NOT match embedded certificate serial {serial_hex}!")
                 print(f"SUGGESTION: Update 'cert_serial_no' to {serial_hex}")
            else:
                 print("Certificate Serial No matches configuration.")
                 
        except ImportError:
            print("To check certificate details, please install 'cryptography': pip install cryptography")
        except Exception as e:
            print(f"Failed to parse embedded certificate: {e}")

    if not all([mchid, cert_serial_no, api_v3_key, private_key]):
        print("Missing required fields.")
        return

    # 2. Try Init
    print("\nAttempting to initialize WeChatPay (triggers cert download)...")
    try:
        # Create a local certs dir for debugging
        cert_dir = os.path.join(os.getcwd(), "backend", "certs_debug")
        os.makedirs(cert_dir, exist_ok=True)
        
        # Enable detailed logging to see HTTP status codes
        logging.getLogger("urllib3").setLevel(logging.DEBUG)
        logging.getLogger("wechatpayv3").setLevel(logging.DEBUG)
        
        wxpay = WeChatPay(
            wechatpay_type=WeChatPayType.NATIVE,
            mchid=mchid,
            private_key=private_key,
            cert_serial_no=cert_serial_no,
            apiv3_key=api_v3_key,
            appid=conf.get("appid") or "",
            notify_url=conf.get("notify_url") or "",
            cert_dir=cert_dir,
            logger=logger
        )
        print("\nSUCCESS! Certificates downloaded/loaded successfully.")
        print(f"CertFiles in {cert_dir}: {os.listdir(cert_dir)}")
        
    except Exception as e:
        print(f"\nFAILURE: {e}")
        # Analysis
        msg = str(e)
        if "platform certificate" in msg:
             print("\nDIAGNOSIS: Generic Failure (No Certs Loaded).")
             print("Please check the logs above for HTTP 401 (Auth Failed) or Decryption Error.")
        
        print("\nTroubleshooting Tips:")
        print("1. invalid signature -> Check your Private Key and Cert Serial No.")
        print("2. decryption failed -> Check your API v3 Key (32 chars).")
        print("3. 401 Unauthorized -> Check MCHID and Serial No.")

if __name__ == "__main__":
    debug_cert_download()
