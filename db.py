import env
from sqlalchemy import create_engine, Engine, ForeignKey
from sqlalchemy import text as RAW_SQL
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
    styles = [Style(id=k, name=v) for k,v in env.TMX_MAP_TAGS.items()]
    with Session(get_engine(echo=False)) as session:
        session.execute(RAW_SQL(f"TRUNCATE TABLE {Style.__tablename__};"))
        session.commit()
        session.add_all(styles)
        session.commit()
    return len(styles)



class Subscription(Base):
    __tablename__ = 'subscription'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(nullable=False)
    channel_id: Mapped[int] = mapped_column(nullable=False)
    role_id: Mapped[int] = mapped_column(nullable=False)
    style_id: Mapped[int] = mapped_column(ForeignKey('style.id'))

def create_subscription(guild_id:int, channel_id:int, role_id:int, style_name:str) -> int:
    # look up style id from name
    style_name = style_name.strip().lower()
    stmt = RAW_SQL(f"SELECT id FROM {Style.__tablename__} WHERE LOWER(name) = '{style_name}' LIMIT 1;")
    with Session(get_engine(echo=False)) as session:
        style_id = session.execute(stmt).scalar_one()
    # insert subscription into table
    sub = Subscription(guild_id=guild_id, channel_id=channel_id, role_id=role_id, style_id=style_id)
    with Session(get_engine(echo=False)) as session:
        session.add(sub)
        session.commit()
        res = session.get_one(Subscription, {'guild_id':guild_id, 'channel_id':channel_id, 'role_id':role_id, 'style_id':style_id})
    # return newly created subscription's autoincremented id
    return res.id
