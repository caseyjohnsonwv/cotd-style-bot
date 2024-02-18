import env
from sqlalchemy import create_engine, Engine
from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy import text as RAW_SQL
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.orm.session import Session


def get_engine(echo:bool=True) -> Engine:
    return create_engine(env.DATABASE_URL, echo=echo)


class Base(DeclarativeBase):
    pass

def create_all():
    engine = get_engine(echo=True)
    Base.metadata.create_all(engine)

def drop_all():
    engine = get_engine(echo=True)
    Base.metadata.drop_all(engine)



class Style(Base):
    __tablename__ = 'style'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False, unique=True)
    def __repr__(self):
        return f"<<Style {self.name} ({self.id})>>"
    
def populate_style_table() -> int:
    styles = [{'id':id, 'name':name} for id,name in env.TMX_MAP_TAGS.items()]
    stmt = pg.insert(Style).values(styles)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Style.id],
        set_={Style.name: stmt.excluded.name}
    )
    with Session(get_engine(echo=False)) as session:
        session.execute(stmt)
        session.commit()
        res = session.query(Style.id).count()
    return res


class Subscription(Base):
    __tablename__ = 'subscription'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    style_id: Mapped[int] = mapped_column(ForeignKey('style.id'))
    __table_args__ = (
        UniqueConstraint('guild_id', 'style_id')
    )

def create_subscription(guild_id:int, channel_id:int, role_id:int, style_name:str) -> int:
    # look up style id from name
    style_name = style_name.strip().lower()
    with Session(get_engine(echo=False)) as session:
        stmt = RAW_SQL(f"SELECT id FROM {Style.__tablename__} WHERE LOWER(name) = '{style_name}' LIMIT 1;")
        style_id = session.execute(stmt).scalar_one()
    # insert subscription into table
    with Session(get_engine(echo=False)) as session:
        stmt = pg.insert(Subscription).values(guild_id=guild_id, channel_id=channel_id, role_id=role_id, style_id=style_id)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Subscription.guild_id, Subscription.style_id],
            set_={Subscription.channel_id: channel_id, Subscription.role_id: role_id}
        )
        sub_id = session.execute(stmt)
        session.commit()
    # return newly created subscription's autoincremented id
    return sub_id
