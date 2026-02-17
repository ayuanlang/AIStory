from sqlalchemy.orm import Session
from app.models.all_models import User, PricingRule, TransactionHistory
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

class BillingService:
    @staticmethod
    def get_pricing_rule(db: Session, task_type: str, provider: str = None, model: str = None) -> PricingRule:
        """
        Finds the pricing rule for the given parameters.
        STRICT MATCH only. 
        If provider/model are provided, we look for that exact combination.
        If they are None, we look for None.
        We do NOT fallback to generic rules if specific ones are missing.
        """
        query = db.query(PricingRule).filter(
            PricingRule.task_type == task_type,
            PricingRule.is_active == True
        )
        
        if provider:
            query = query.filter(PricingRule.provider == provider)
        else:
            query = query.filter(PricingRule.provider == None)
            
        if model:
            query = query.filter(PricingRule.model == model)
        else:
            query = query.filter(PricingRule.model == None)
            
        return query.first()

    @staticmethod
    def estimate_cost(db: Session, task_type: str, provider: str = None, model: str = None, details: dict = None) -> int:
        rule = BillingService.get_pricing_rule(db, task_type, provider, model)
        if not rule:
            error_msg = f"No pricing rule found for task: {task_type}, provider: {provider}, model: {model}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail="Pricing configuration error. Please contact support.")

        # Advanced Calculation Logic
        try:
            # LLM Dual Pricing (Input/Output Tokens) - Applies to any text/vision task with token details
            task_type_allowed_for_tokens = task_type in ['llm_chat', 'analysis', 'analysis_character']
            if task_type_allowed_for_tokens and details and ('input_tokens' in details or 'output_tokens' in details):
                input_tokens = details.get('input_tokens', 0)
                output_tokens = details.get('output_tokens', 0)
                
                # If specific input/output costs are set, use them
                if rule.cost_input is not None and rule.cost_output is not None:
                     # Calculate based on unit_type (usually per_million_tokens for LLMs)
                    divisor = 1_000_000.0 if rule.unit_type == 'per_million_tokens' else \
                              1_000.0 if rule.unit_type == 'per_1k_tokens' else 1.0
                    
                    cost_in = (float(input_tokens) / divisor) * float(rule.cost_input)
                    cost_out = (float(output_tokens) / divisor) * float(rule.cost_output)
                    
                    # User requirement: Calculate exact cost for small amounts (e.g. 0.3M -> 0.3 * unit_cost)
                    # However, credits are strictly Integers.
                    # We will sum them first as float, then round.
                    # Standard policy: Ceil to 1 if > 0 but < 1? Or standard round?
                    # "0.3M should be 1/3" implies precise ratio.
                    # If cost_input=100 (for 1M), then 0.3M -> 30 credits.
                    # If cost_input=1 (for 1M), then 0.3M -> 0.3 credits -> 0 or 1?
                    # Generally billing systems floor or round. 
                    # If the user emphasizes "0.3M should be 1/3", they likely have high unit costs (like 200/250)
                    # So precise float calculation is key.
                    
                    total_calculated = cost_in + cost_out
                    
                    # If total > 0 but < 1, we must charge at least 1 if we charge anything?
                    # Or we allow 0 for very small usage? 
                    # Usually 'max(1, ...)' is safe to avoid free usage loopholes.
                    # But if total is 60.5, we should probably round to 61 or 60.
                    
                    return int(max(1, round(total_calculated)))

            # Standard Unit Multipliers
            quantity = 1.0
            if details:
                if rule.unit_type == 'per_second':
                    quantity = float(details.get('duration_seconds', 0))
                elif rule.unit_type == 'per_minute':
                    quantity = float(details.get('duration_seconds', 0)) / 60.0
                elif rule.unit_type == 'per_token':
                    quantity = float(details.get('total_tokens', 0))
                elif rule.unit_type == 'per_1k_tokens':
                    quantity = float(details.get('total_tokens', 0)) / 1000.0
                elif rule.unit_type == 'per_million_tokens':
                    quantity = float(details.get('total_tokens', 0)) / 1_000_000.0
            
            total = float(rule.cost) * quantity
            return int(max(1, round(total))) if total > 0 else 0

        except Exception as e:
            logger.error(f"Error calculating cost: {e}")
            return rule.cost


    @staticmethod
    def check_balance(db: Session, user_id: int, task_type: str, provider: str = None, model: str = None):
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
             raise HTTPException(status_code=404, detail="User not found")
        
        # Estimate base cost
        cost = BillingService.estimate_cost(db, task_type, provider, model)
        # Check
        BillingService.check_can_proceed(user, cost)

    @staticmethod
    def check_can_proceed(user: User, cost: int):
        """
        Raises HTTPException if user doesn't have enough credits.
        """
        if user.credits is None:
            user.credits = 0
            
        if user.credits < cost:
            raise HTTPException(
                status_code=402, 
                detail=f"Insufficient credits. Required: {cost}, Available: {user.credits}. Please top up."
            )
        return True

    @staticmethod
    def deduct_credits(
        db: Session, 
        user_id: int, 
        task_type: str, 
        provider: str = None, 
        model: str = None, 
        details: dict = None
    ) -> TransactionHistory:
        """
        Deducts credits from user and logs transaction.
        """
        # Re-fetch user to lock/ensure latest state
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        final_cost = BillingService.estimate_cost(db, task_type, provider, model, details=details)
        
        if user.credits < final_cost:
             raise HTTPException(status_code=402, detail="Insufficient credits during deduction.")
             
        user.credits -= final_cost
        
        # Log Transaction
        transaction = TransactionHistory(
            user_id=user_id,
            amount=-final_cost,
            balance_after=user.credits,
            task_type=task_type,
            provider=provider,
            model=model,
            details=details or {}
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        logger.info(f"Deducted {final_cost} credits from user {user_id} for {task_type}. New Balance: {user.credits}")
        return transaction

    @staticmethod
    def log_failed_transaction(
        db: Session, 
        user_id: int, 
        task_type: str, 
        provider: str = None, 
        model: str = None, 
        error_msg: str = None,
        details: dict = None
    ):
        """
        Logs a failed transaction for visibility in recent transactions.
        """
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.error(f"Cannot log failure for non-existent user {user_id}")
                return

            fail_details = details or {}
            fail_details["status"] = "FAILED"
            fail_details["error"] = str(error_msg)[:500] # Truncate error

            transaction = TransactionHistory(
                user_id=user_id,
                amount=0,
                balance_after=user.credits or 0,
                task_type=task_type,
                provider=provider,
                model=model,
                details=fail_details
            )
            db.add(transaction)
            db.commit()
            logger.info(f"Logged failed transaction for user {user_id}: {error_msg}")
        except Exception as e:
            logger.error(f"Failed to log transaction failure: {e}")
            db.rollback()

billing_service = BillingService()
