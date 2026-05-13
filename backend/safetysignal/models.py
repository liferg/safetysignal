from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from safetysignal.db import Base


class Drug(Base):
    __tablename__ = "drugs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    rxnorm_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    atc_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    therapeutic_area: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    reports: Mapped[list["Report"]] = relationship(back_populates="drug")


class AdverseEvent(Base):
    __tablename__ = "adverse_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meddra_pt: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    meddra_soc: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    reports: Mapped[list["Report"]] = relationship(back_populates="adverse_event")


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint(
            "openfda_report_id",
            "drug_id",
            "ae_id",
            name="uq_reports_report_drug_ae",
        ),
        Index("idx_reports_drug_ae", "drug_id", "ae_id"),
        Index("idx_reports_ae", "ae_id"),
        Index("idx_reports_drug", "drug_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    openfda_report_id: Mapped[str] = mapped_column(Text, nullable=False)
    drug_id: Mapped[int] = mapped_column(
        ForeignKey("drugs.id"), nullable=False
    )
    ae_id: Mapped[int] = mapped_column(
        ForeignKey("adverse_events.id"), nullable=False
    )
    age: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    sex: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    serious: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    drug: Mapped["Drug"] = relationship(back_populates="reports")
    adverse_event: Mapped["AdverseEvent"] = relationship(back_populates="reports")
