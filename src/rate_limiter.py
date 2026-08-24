import asyncio
import time
import logging

logger = logging.getLogger(__name__)

class TokenBucketRateLimiter:
    """
    An async rate limiter using the Token Bucket algorithm to enforce
    Requests Per Minute (RPM) and Tokens Per Minute (TPM) constraints.
    """
    def __init__(self, max_rpm: float = None, max_tpm: float = None):
        self.max_rpm = max_rpm
        self.max_tpm = max_tpm
        
        # RPM bucket configuration
        self.rpm_capacity = max_rpm if max_rpm is not None else 0.0
        self.rpm_tokens = self.rpm_capacity
        self.rpm_last_refill = time.monotonic()
        
        # TPM bucket configuration
        self.tpm_capacity = max_tpm if max_tpm is not None else 0.0
        self.tpm_tokens = self.tpm_capacity
        self.tpm_last_refill = time.monotonic()
        
        self.lock = asyncio.Lock()

    def _refill(self):
        """Refills both RPM and TPM buckets based on elapsed time."""
        now = time.monotonic()
        
        # Refill RPM
        if self.max_rpm and self.max_rpm > 0:
            elapsed = now - self.rpm_last_refill
            refill_amount = elapsed * (self.max_rpm / 60.0)
            self.rpm_tokens = min(self.rpm_capacity, self.rpm_tokens + refill_amount)
            self.rpm_last_refill = now
            
        # Refill TPM
        if self.max_tpm and self.max_tpm > 0:
            elapsed = now - self.tpm_last_refill
            refill_amount = elapsed * (self.max_tpm / 60.0)
            self.tpm_tokens = min(self.tpm_capacity, self.tpm_tokens + refill_amount)
            self.tpm_last_refill = now

    async def acquire(self, estimated_tokens: int = 1000):
        """
        Acquire rate limiting clearance. Block if limits are currently exceeded.
        """
        # 1. RPM check
        if self.max_rpm and self.max_rpm > 0:
            while True:
                async with self.lock:
                    self._refill()
                    if self.rpm_tokens >= 1.0:
                        self.rpm_tokens -= 1.0
                        break
                    # Wait duration to get 1 token
                    wait_time = (1.0 - self.rpm_tokens) / (self.max_rpm / 60.0)
                logger.debug(f"RPM limit reached. Waiting for {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

        # 2. TPM check
        if self.max_tpm and self.max_tpm > 0:
            while True:
                async with self.lock:
                    self._refill()
                    # We allow request if bucket is positive. If the request consumes
                    # more than current capacity, the bucket goes negative and subsequent
                    # requests will wait.
                    if self.tpm_tokens >= 0:
                        break
                    # Wait duration until bucket refills to 0
                    wait_time = -self.tpm_tokens / (self.max_tpm / 60.0)
                logger.debug(f"TPM limit reached. Waiting for {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

    async def update_tokens(self, actual_tokens: int):
        """
        Updates the TPM bucket after a request completes, charging the actual tokens consumed.
        """
        if not self.max_tpm or self.max_tpm <= 0:
            return
        async with self.lock:
            self._refill()
            self.tpm_tokens -= actual_tokens
            logger.debug(f"Consumed {actual_tokens} tokens. Current TPM bucket balance: {self.tpm_tokens:.1f}")
