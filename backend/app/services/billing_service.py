from sqlalchemy.orm import Session
from app.models.all_models import User, PricingRule, TransactionHistory
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

class BillingService:
    @staticmethod
    def get_pricing_rule(db: Session, task_type: str, provider: str = None, model: str = None) -> PricingRule:
        """
        Finds the most specific pricing rule for the given parameters.
        Priority:
        1. Exact match (task_type, provider, model)
        2. Provider match (task_type, provider, NULL)
        3. Generic match (task_type, NULL, NULL)
        """
        # 1. Exact Match
        if provider and model:
            rule = db.query(PricingRule).filter(
                PricingRule.task_type == task_type,
                PricingRule.provider == provider,
                PricingRule.model == model,
                PricingRule.is_active == True
            ).first()
            if rule: return rule
            
        # 2. Provider Match
        if provider:
            rule = db.query(PricingRule).filter(
                PricingRule.task_type == task_type,
                PricingRule.provider == provider,
                PricingRule.model == None,
                PricingRule.is_active == True
            ).first()
            if rule: return rule
            
        # 3. Generic Match
        rule = db.query(PricingRule).filter(
            PricingRule.task_type == task_type,
            PricingRule.provider == None,
            PricingRule.model == None,
            PricingRule.is_active == True
        ).first()
        
        return rule

    @staticmethod
    def estimate_cost(db: Session, task_type: str, provider: str = None, model: str = None, details: dict = None) -> int:
        rule = BillingService.get_pricing_rule(db, task_type, provider, model)
        if not rule:
            # Fallback defaults if no rule exists at all
            defaults = {
                "image_gen": 5,
                "video_gen": 20,
                "llm_chat": 1,
                "analysis": 1
            }
            return defaults.get(task_type, 1)

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
                    divisor = 1_000_000 if rule.unit_type == 'per_million_tokens' else \
                              1_000 if rule.unit_type == 'per_1k_tokens' else 1
                    
                    cost_in = (input_tokens / divisor) * rule.cost_input
                    cost_out = (output_tokens / divisor) * rule.cost_output
                    return int(max(1, cost_in + cost_out)) # Ensure at least 1 credit if used

            # Standard Unit Multipliers
            quantity = 1
            if details:
                if rule.unit_type == 'per_second':
                    quantity = details.get('duration_seconds', 0)
                elif rule.unit_type == 'per_minute':
                    quantity = details.get('duration_seconds', 0) / 60
                elif rule.unit_type == 'per_token':
                    quantity = details.get('total_tokens', 0)
                elif rule.unit_type == 'per_1k_tokens':
                    quantity = details.get('total_tokens', 0) / 1000
                elif rule.unit_type == 'per_million_tokens':
                    quantity = details.get('total_tokens', 0) / 1_000_000
            
            total = rule.cost * quantity
            return int(max(1, total)) if total > 0 else 0

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

billing_service = BillingService()
