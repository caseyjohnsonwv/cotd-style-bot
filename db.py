import env
from sqlalchemy import create_engine, Engine, ForeignKey
from sqlalchemy import text as RAW_SQL
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.orm.session import Session


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
    
def populate_style_table() -> int:
    styles = [Style(id=k, name=v) for k,v in env.TMX_MAP_TAGS]
    with Session(get_engine(echo=False)) as session:
        session.execute(RAW_SQL(f"TRUNCATE TABLE {Style.__tablename__};"))
        session.commit()
        session.add_all(styles)
        session.commit()
    with Session(get_engine(echo=False)) as session:
        num_records = session.execute(RAW_SQL(f"SELECT COUNT(*) FROM {Style.__tablename__}")).scalar_one()
    return num_records


# class Subscription(Base):
#     __tablename__ = 'subscription'
#     id: Mapped[str] = mapped_column(primary_key=True)
#     guild_id: Mapped[str] = mapped_column(nullable=False)
#     channel_id: Mapped[str] = mapped_column(nullable=False)
#     role_id: Mapped[str] = mapped_column(nullable=False)
#     style_id: Mapped[int] = mapped_column(nullable=False)


def create_all():
    engine = get_engine(echo=True)
    Base.metadata.create_all(engine)

def drop_all():
    engine = get_engine(echo=True)
    Base.metadata.drop_all(engine)
