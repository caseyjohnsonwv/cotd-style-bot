from datetime import datetime
import json
from typing import List
from sqlalchemy import create_engine, Engine, Row
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy import text as RAW_SQL, or_ as SQL_OR, and_ as SQL_AND, func as F
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.orm.session import Session
import env



def get_engine(echo:bool=True) -> Engine:
    return create_engine(env.DATABASE_URL, echo=echo)



def do_startup_actions():
    create_all()
    populate_style_table()



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
    # load global map styles scraped from TMX
    with open('dat/styles.json', 'r') as f:
        j = dict(json.load(f))
    styles = [{'id':int(k), 'name':v} for k,v in j.items()]
    # dump to database table
    stmt = pg.insert(Style).values(styles)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Style.id],
        set_={Style.name: stmt.excluded.name}
    )
    with Session(get_engine()) as session:
        session.execute(stmt)
        session.commit()
        res = session.query(Style.id).count()
    return res

def get_all_style_names() -> List[str]:
    with Session(get_engine()) as session:
        res = session.query(Style).order_by(Style.name).all()
        style_names = [row.name for row in res]
    return style_names



class Subscription(Base):
    __tablename__ = 'subscription'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    style_id: Mapped[int] = mapped_column(ForeignKey('style.id'))
    __table_args__ = (
        UniqueConstraint('guild_id', 'style_id'),
    )
    def __repr__(self):
        return f"<<Subscription {self.id} for style {self.style_id}>>"

def create_subscription(guild_id:int, channel_id:int, role_id:int, style_name:str) -> int:
    # look up style id from name
    style_name = style_name.strip().lower()
    with Session(get_engine(echo=False)) as session:
        stmt = RAW_SQL(f"SELECT id FROM {Style.__tablename__} WHERE LOWER(name) = '{style_name}' LIMIT 1;")
        style_id = session.execute(stmt).scalar_one()
    # insert subscription into table
    with Session(get_engine()) as session:
        stmt = pg.insert(Subscription).values(guild_id=guild_id, channel_id=channel_id, role_id=role_id, style_id=style_id)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Subscription.guild_id, Subscription.style_id],
            set_={Subscription.channel_id: channel_id, Subscription.role_id: role_id}
        )
        sub_id = session.execute(stmt)
        session.commit()
    # return newly created subscription's autoincremented id
    return sub_id

def delete_subscription(guild_id:int, style_name:str=None, role_id:int=None) -> bool:
    assert style_name or role_id
    with Session(get_engine()) as session:
        res = session.query(Subscription) \
            .where(Subscription.style_id == Style.id) \
            .where(Subscription.guild_id == guild_id)
        if style_name:
            res = res.where(Style.name.ilike(style_name))
        if role_id:
            res = res.where(Subscription.role_id == role_id)
        res = res.first()
        print(res.style_id, res.role_id)
        if res:
            session.delete(res)
            session.commit()
    return res is not None

def get_subscriptions_for_styles(style_names:List[str]) -> List[Subscription]:
    with Session(get_engine()) as session:
        where_clauses = [session.query(Subscription).where(Style.name.ilike(name)) for name in style_names]
        res = session.query(Subscription) \
            .where(Subscription.style_id == Style.id) \
            .where(SQL_OR(where_clauses)) \
            .all()
    return res



class Track(Base):
    __tablename__ = 'track'
    uid: Mapped[str] = mapped_column(primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime, unique=True)
    name: Mapped[str] = mapped_column(nullable=False)
    author: Mapped[str] = mapped_column(nullable=False)
    author_time: Mapped[float] = mapped_column(nullable=False)
    thumbnail_url: Mapped[str] = mapped_column()
    load_date_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    def __repr__(self):
        return f"<<Track {self.map_uid} from {self.date}>>"
    
class TrackTagsReference(Base):
    __tablename__ = 'track_tags_reference'
    track_uid: Mapped[str] = mapped_column(ForeignKey('track.uid'), primary_key=True)
    style_id: Mapped[int] = mapped_column(ForeignKey('style.id'), primary_key=True)
    def __repr__(self):
        return f"<<Track {self.track_uid} | Tag {self.style_id}>>"

def create_track(uid:str, date:datetime, name:str, author:str, author_time:float, thumbnail_url:str):
    # truncate totd date
    date = datetime(date.year, date.month, date.day)
    with Session(get_engine()) as session:
        stmt = pg.insert(Track).values(
            uid=uid,
            date=date,
            name=name,
            author=author,
            author_time=author_time,
            thumbnail_url=thumbnail_url,
            load_date_time=datetime.utcnow()
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Track.date],
            set_={
                Track.uid: stmt.excluded.uid,
                Track.name: stmt.excluded.name,
                Track.author: stmt.excluded.author,
                Track.author_time: stmt.excluded.author_time,
                Track.thumbnail_url: stmt.excluded.thumbnail_url,
                Track.load_date_time: stmt.excluded.load_date_time,
            },
        )
        session.execute(stmt)
        session.commit()
    return uid

def create_track_tags_reference(track_uid:str, track_tags:List[int]) -> int:
    tag_refs = [{'track_uid':track_uid, 'style_id':style_id} for style_id in track_tags]
    with Session(get_engine()) as session:
        stmt = pg.insert(TrackTagsReference).values(tag_refs).on_conflict_do_nothing()
        session.execute(stmt)
        session.commit()
    return len(track_tags)

def get_track_by_date(date:datetime) -> Track:
    date = datetime(date.year, date.month, date.day)
    with Session(get_engine()) as session:
        res = session.query(Track).where(Track.date == date).first()
    return res



# crud function to put all this notification logic in one query

def get_notification_payloads() -> List[Row]:
    now = datetime.utcnow()
    current_date = datetime(now.year, now.month, now.day)
    with Session(get_engine()) as session:
        res = session.query(
            Subscription.role_id.label('role_id'),
            Subscription.channel_id.label('channel_id'),
            Track.name.label('track_name'),
            Track.author.label('author'),
            Track.author_time.label('author_time'),
            Track.thumbnail_url.label('thumbnail_url'),
            F.array_agg(Style.name, type_=pg.ARRAY(String)).label('track_tags')
        ) \
        .where(Track.date == current_date) \
        .where(TrackTagsReference.track_uid == Track.uid) \
        .where(TrackTagsReference.style_id == Subscription.style_id) \
        .where(TrackTagsReference.style_id == Style.id) \
        .group_by(
            Subscription.role_id,
            Subscription.channel_id,
            Track.name,
            Track.author,
            Track.author_time,
            Track.thumbnail_url,
        ) \
        .all()
    return res
