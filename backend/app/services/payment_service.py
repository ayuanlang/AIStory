import logging
import json
from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from wechatpayv3 import WeChatPay, WeChatPayType
except ImportError:
    WeChatPay = None
    WeChatPayType = None
    logger.warning("wechatpayv3 not installed")

class PaymentService:
    def __init__(self):
        self.wxpay = None
        self._init_wxpay()

    def _init_wxpay(self):
        if not WeChatPay:
            return
        
        # Check essential config
        if not all([settings.WECHAT_APPID, settings.WECHAT_MCHID, settings.WECHAT_API_V3_KEY, settings.WECHAT_PRIVATE_KEY_PATH, settings.WECHAT_CERT_SERIAL_NO]):
            logger.warning("WeChat Pay config missing or incomplete. Real payments will fail.")
            return

        try:
            with open(settings.WECHAT_PRIVATE_KEY_PATH, encoding="utf-8") as f:
                private_key = f.read()
            
            logger.info("Initializing WeChatPay...")
            self.wxpay = WeChatPay(
                wechatpay_type=WeChatPayType.NATIVE,
                mchid=settings.WECHAT_MCHID,
                private_key=private_key,
                cert_serial_no=settings.WECHAT_CERT_SERIAL_NO,
                apiv3_key=settings.WECHAT_API_V3_KEY,
                appid=settings.WECHAT_APPID,
                notify_url=settings.WECHAT_NOTIFY_URL,
                logger=logger
            )
        except Exception as e:
            logger.error(f"Failed to init WeChatPay: {e}")

    def create_native_order(self, order_no: str, amount_cny: int, description: str) -> str:
        """
        Returns code_url for QR generation or None if failed.
        """
        if not self.wxpay:
            logger.error("WeChat Pay not initialized")
            return None
        
        # Amount in Fen
        amount_fen = int(amount_cny * 100)
        
        try:
            code, message = self.wxpay.pay(
                description=description,
                out_trade_no=order_no,
                amount={'total': amount_fen},
                pay_type=WeChatPayType.NATIVE
            )
            
            if code == 200:
                res = json.loads(message)
                return res.get('code_url')
            else:
                logger.error(f"WeChat Pay Create Error: {code} - {message}")
                return None
        except Exception as e:
            logger.error(f"Create order exception: {e}")
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
