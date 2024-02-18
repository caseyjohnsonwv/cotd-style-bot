import env
from sqlalchemy import create_engine, Engine, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def get_engine(echo:bool=True) -> Engine:
    return create_engine(env.DATABASE_URL, echo=echo)


class Base(DeclarativeBase):
    pass


class Style(Base):
    __tablename__ = 'style'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False, unique=True)
    def __repr__(self):
        return f"<<Style {self.name} ({self.id})>>"


# class Subscription(Base):
#     __tablename__ = 'subscription'
#     id: Mapped[str] = mapped_column(primary_key=True)
#     guild_id: Mapped[str] = mapped_column(nullable=False)
#     channel_id: Mapped[str] = mapped_column(nullable=False)
#     role_id: Mapped[str] = mapped_column(nullable=False)
#     style_id: Mapped[int] = mapped_column(nullable=False)


def create_all():
    engine = get_engine(echo=False)
    Base.metadata.create_all(engine)

def drop_all():
    engine = get_engine(echo=False)
    Base.metadata.drop_all(engine)
