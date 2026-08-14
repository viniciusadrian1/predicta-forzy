"""Seed inicial do catalogo: planta, area, motor MTR-001 e usuarios.

Idempotente - pode ser executado multiplas vezes com seguranca:

    python -m app.scripts.seed
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.core.logging import configure_logging
from app.core.security import hash_password
from app.infra.db.base import catalog_session_factory
from app.modules.assets.models import Area, Asset, Plant
from app.modules.auth.models import User

logger = logging.getLogger("forzy.seed")

# Usuarios de demonstracao (usuario, senha, papel, nome completo).
# As senhas sao protegidas por hashing argon2 no momento do seed.
_SEED_USERS: tuple[tuple[str, str, str, str], ...] = (
    ("admin", "admin123", "admin", "Administrador do Sistema"),
    ("engenheiro", "eng123", "engineer", "Engenheiro de Manutencao"),
    ("operador", "operador123", "operator", "Operador de Planta"),
    ("viewer", "viewer123", "viewer", "Visualizador"),
)


async def seed() -> None:
    """Cria a planta, a area e o motor MTR-001 se ainda nao existirem."""
    async with catalog_session_factory() as session:
        plant = (
            await session.execute(select(Plant).where(Plant.code == "PLANT-SP"))
        ).scalar_one_or_none()
        if plant is None:
            plant = Plant(
                name="Planta Sao Paulo",
                code="PLANT-SP",
                location="Sao Paulo - SP, Brasil",
            )
            session.add(plant)
            await session.flush()
            logger.info("Planta criada: %s", plant.code)

        area = (
            await session.execute(select(Area).where(Area.code == "AREA-BOMBAS"))
        ).scalar_one_or_none()
        if area is None:
            area = Area(plant_id=plant.id, name="Sala de Bombas", code="AREA-BOMBAS")
            session.add(area)
            await session.flush()
            logger.info("Area criada: %s", area.code)

        asset = (
            await session.execute(select(Asset).where(Asset.tag == "MTR-001"))
        ).scalar_one_or_none()
        if asset is None:
            asset = Asset(
                tag="MTR-001",
                asset_type="motor",
                name="Motor da bomba de teste",
                manufacturer="WEG",
                model="W22 IR3 Premium",
                serial_number="WEG-2024-0001",
                power_kw=7.5,
                voltage_v=220.0,
                nominal_current_a=25.4,
                nominal_rpm=1755,
                connection_type="triangulo",
                insulation_class="F",
                ip_rating="IP55",
                weight_kg=62.0,
                plant_id=plant.id,
                area_id=area.id,
                position_x=0.5,
                position_y=0.42,
                status="ok",
                datasheet_url="/docs/sensor_vibracao_pepperl_fuchs.pdf",
            )
            session.add(asset)
            logger.info("Ativo criado: %s", asset.tag)

        # Sensores fisicos da Forzy (S1/S2) - alimentados pela API HTTP externa.
        for tag, sensor_name, pos_x in (
            ("MTR-F01", "Motor físico Forzy — sensor S1", 0.32),
            ("MTR-F02", "Motor físico Forzy — sensor S2", 0.68),
        ):
            existing = (
                await session.execute(select(Asset).where(Asset.tag == tag))
            ).scalar_one_or_none()
            if existing is None:
                session.add(
                    Asset(
                        tag=tag,
                        asset_type="motor",
                        name=sensor_name,
                        manufacturer="Forzy",
                        voltage_v=220.0,
                        plant_id=plant.id,
                        area_id=area.id,
                        position_x=pos_x,
                        position_y=0.68,
                        status="unknown",
                    )
                )
                logger.info("Ativo criado: %s", tag)

        for username, password, role, full_name in _SEED_USERS:
            user = (
                await session.execute(select(User).where(User.username == username))
            ).scalar_one_or_none()
            if user is None:
                session.add(
                    User(
                        username=username,
                        password_hash=hash_password(password),
                        role=role,
                        full_name=full_name,
                    )
                )
                logger.info("Usuario criado: %s (papel: %s)", username, role)

        await session.commit()
    logger.info("Seed concluido com sucesso.")


def main() -> None:
    configure_logging()
    asyncio.run(seed())


if __name__ == "__main__":
    main()
