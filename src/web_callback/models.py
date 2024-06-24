from pydantic import BaseModel


class Property(BaseModel):
    IMEI: str
    ЛИТР: int


class PaymentResult(BaseModel):
    code: int
    message: str = None
    details: str = None


class PaymentData(BaseModel):
    regPayNum: str
    property: Property | None
    rrn: str | None
    irn: str | None
    approvalCode: str
    cardPan: str | None
    amount: int
    state: str
    result: PaymentResult
    created: str | None
