import logging
import json
from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from wechatpayv3 import WeChatPay, WeChatPayType
except ImportError:
    WeChatPay = None
    WeChatPayType = None
    
# Avoid conflict with the top level name if imported again in the block
# Actually, the global variable works.

class PaymentService:
    def __init__(self):
        self.wxpay = None
        self.config = {}
        # delaying _init_wxpay call until first use or config update might refer this?
        # but __init__ calls it. That's fine.
        self._init_wxpay()

    def update_config(self, config: dict):
        """
        Update the payment service configuration dynamically.
        config: {
            "mchid": str,
            "appid": str,
            "api_v3_key": str,
            "cert_serial_no": str,
            "private_key": str,
            "notify_url": str,
            "use_mock": bool
        }
        """
        self.config = config
        self._init_wxpay()

    def _init_wxpay(self):
        global WeChatPay, WeChatPayType
        if WeChatPay is None:
            try:
                from wechatpayv3 import WeChatPay, WeChatPayType
            except ImportError:
                WeChatPay = None
                WeChatPayType = None

        if WeChatPay is None:
            logger.error("CRITICAL: wechatpayv3 library not found! 'pip install wechatpayv3' is required.")
            return

        # Ensure certs directory exists
        cert_dir = settings.BASE_DIR / "certs"
        if not cert_dir.exists():
            cert_dir.mkdir(parents=True, exist_ok=True)
        
        # Priority: Dynamic Config > Environment Variables
        use_mock = self.config.get('use_mock', False)
        logger.info(f"PaymentService Re-Init. Mock={use_mock}")

        if use_mock:
            logger.info("PaymentService: Using Mock/Sandbox Mode.")
            self.wxpay = None
            return

        mchid = self.config.get('mchid') or settings.WECHAT_MCHID
        appid = self.config.get('appid') or settings.WECHAT_APPID
        api_v3_key = self.config.get('api_v3_key') or settings.WECHAT_API_V3_KEY
        cert_serial_no = self.config.get('cert_serial_no') or settings.WECHAT_CERT_SERIAL_NO
        notify_url = self.config.get('notify_url') or settings.WECHAT_NOTIFY_URL
        private_key = self.config.get('private_key')

        # If private_key not in config, try reading file from settings path
        if not private_key and settings.WECHAT_PRIVATE_KEY_PATH:
            try:
                with open(settings.WECHAT_PRIVATE_KEY_PATH, encoding="utf-8") as f:
                    private_key = f.read()
            except Exception as e:
                logger.warning(f"Could not read private key file: {e}")

        # Check essential config
        missing_fields = []
        if not mchid: missing_fields.append('mchid')
        if not appid: missing_fields.append('appid')
        if not api_v3_key: missing_fields.append('api_v3_key')
        if not private_key: missing_fields.append('private_key (path or content)')
        if not cert_serial_no: missing_fields.append('cert_serial_no')
        
        if missing_fields:
            logger.warning(
                "WeChat Pay config incomplete. Missing: %s. Real payments will fail. "
                "Set env vars WECHAT_MCHID, WECHAT_APPID, WECHAT_API_V3_KEY, WECHAT_PRIVATE_KEY_PATH (or provide private_key in dynamic config), "
                "WECHAT_CERT_SERIAL_NO. For local/dev, enable use_mock=true.",
                ", ".join(missing_fields),
            )
            # Ensure we don't leave a stale instance if config became invalid
            self.wxpay = None
            return

        # Helper to clean PEM key
        def _clean_pem(key_str):
            if not key_str: return key_str
            try:
                # Keep only the Private Key block if multiple blocks exist
                if "-----BEGIN PRIVATE KEY-----" in key_str:
                    start = key_str.find("-----BEGIN PRIVATE KEY-----")
                    end_marker = "-----END PRIVATE KEY-----"
                    end = key_str.find(end_marker)
                    if start != -1 and end != -1:
                        return key_str[start : end + len(end_marker)]
                return key_str.strip()
            except:
                return key_str

        private_key = _clean_pem(private_key)

        try:
            logger.info(f"Initializing WeChatPay with MCHID={mchid}, APPID={appid}, CERT_SERIAL={cert_serial_no}")
            
            # Note: The wechatpayv3 library attempts to download platform certs on init.
            # If it fails, it raises the "No wechatpay platform certificate" error.
            # This usually means the APIV3 Key is wrong, or the Merchant Cert Serial No does not match the Private Key.
            # Or the network request to WeChat failed.
            
            self.wxpay = WeChatPay(
                wechatpay_type=WeChatPayType.NATIVE,
                mchid=mchid,
                private_key=private_key,
                cert_serial_no=cert_serial_no,
                apiv3_key=api_v3_key,
                appid=appid,
                notify_url=notify_url,
                cert_dir=str(cert_dir), # Cache certs
                logger=logger
            )
            logger.info("WeChatPay initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to init WeChatPay: {e}. Possible causes: Wrong APIV3 Key, or Cert Serial No mismatch.", exc_info=True)
            self.wxpay = None

    def create_native_order(self, order_no: str, amount_cny: int, description: str) -> str:
        """
        Returns code_url for QR generation or None if failed.
        If in Mock mode, returns a mock URL beginning with 'weixin://mock/'
        """
        # Check Mock Mode
        use_mock = self.config.get('use_mock', False)
        logger.info(f"Creating Order {order_no}: Mock={use_mock}, Amount={amount_cny}")
        
        if use_mock:
             # Return a special mock URL that the frontend can recognize, 
             # OR just a valid QR string that scans to nothing but frontend displays a "Simulate Logic"
             # Actually, for standard flow, we return a string.
             # If we want to simulate scanning, maybe we render a QR code that triggers a "Click to Pay" action?
             # For now, return a mock URL.
             return f"weixin://mock/pay?order={order_no}"

        if not self.wxpay:
            # We already logged *why* it wasn't initialized in _init_wxpay (e.g. missing fields or exception)
            # But let's log the current config state again here for debugging
            logger.error(f"WeChat Pay not initialized. Mock={use_mock}. Config state: MCHID={bool(self.config.get('mchid'))}, APPID={bool(self.config.get('appid'))}, KEY={bool(self.config.get('api_v3_key'))}, CERT={bool(self.config.get('cert_serial_no'))}, PRIV_KEY={bool(self.config.get('private_key'))}")
            return None
        
        # Amount in Fen
        amount_fen = int(amount_cny * 100)
        
        try:
            logger.info(f"Calling WeChat API for {order_no} with amount {amount_fen} fen")
            code, message = self.wxpay.pay(
                description=description,
                out_trade_no=order_no,
                amount={'total': amount_fen},
                pay_type=WeChatPayType.NATIVE
            )
            logger.info(f"WeChat API Response Code: {code}")
            
            if code == 200:
                res = json.loads(message)
                code_url = res.get('code_url')
                logger.info(f"Received code_url: {code_url}")
                return code_url
            else:
                logger.error(f"WeChat Pay Create Error: {code} - {message}")
                return None
        except Exception as e:
            logger.error(f"Create order exception: {e}", exc_info=True)
            return None

    def query_order(self, order_no: str) -> str:
        """
        Returns status: SUCCESS, REFUND, NOTPAY, CLOSED, REVOKED, PAYERROR or None
        """
        if not self.wxpay:
            return None
            
        try:
            code, message = self.wxpay.query(out_trade_no=order_no)
            if code == 200:
                res = json.loads(message)
                return res.get('trade_state')
            else:
                logger.error(f"WeChat Pay Query Error: {code} - {message}")
                return None
        except Exception as e:
            logger.error(f"Query order exception: {e}")
            return None

    def parse_notify(self, headers, body):
        """
        Verifies signature and decrypts the message.
        """
        if not self.wxpay:
            return None
        
        try:
            # Helper method in library usually handles verify+decrypt
            result = self.wxpay.callback(headers, body)
            return result
        except Exception as e:
            logger.error(f"Notify callback exception: {e}")
            return None

payment_service = PaymentService()
