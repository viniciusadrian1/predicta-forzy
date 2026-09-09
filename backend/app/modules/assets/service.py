"""Regras de negocio do modulo de ativos."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.modules.assets.models import Area, Asset, Plant
from app.modules.assets.repository import AssetRepository
from app.modules.assets.schemas import AreaIn, AssetIn, AssetUpdate, PlantIn
from app.modules.governance.repository import TagAuditRepository


class AssetAlreadyExistsError(Exception):
    """Ja existe um ativo com a TAG informada."""


class AssetNotFoundError(Exception):
    """Nenhum ativo encontrado para a TAG informada."""


class PlantNotFoundError(Exception):
    """A planta referenciada nao existe."""


# Pior estado vence ao consolidar um conjunto a partir dos seus pontos.
_STATUS_RANK = {"unknown": 0, "ok": 1, "warning": 2, "critical": 3}


def rollup_status(asset: Asset, points: list[Asset]) -> str:
    """Status de um EQUIPAMENTO a partir dos seus pontos de medicao.

    Um conjunto (ex.: o motor-bomba da Forzy) nao tem telemetria propria - quem
    mede sao os mancais -, entao o avaliador nunca toca no status dele e ele
    ficaria "desconhecido" para sempre. Derivar aqui, no servico, mantem a
    arvore lateral, a planta, os KPIs e a tela do ativo dizendo a MESMA coisa.
    """
    if not points:
        return asset.status
    return max(
        (p.status for p in points),
        key=lambda status: _STATUS_RANK.get(status, 0),
    )


class AssetService:
    """Orquestra as operacoes do catalogo de ativos."""

    def __init__(self, repository: AssetRepository) -> None:
        self._repo = repository

    # ------------------------- Assets -------------------------
    async def list_assets(self) -> list[Asset]:
        assets = await self._repo.list_assets()
        by_parent: dict[str, list[Asset]] = {}
        for asset in assets:
            if asset.parent_tag:
                by_parent.setdefault(asset.parent_tag, []).append(asset)
        for asset in assets:
            asset.status = rollup_status(asset, by_parent.get(asset.tag, []))
        return assets

    async def _load_asset(self, tag: str) -> Asset:
        """A ENTIDADE crua, para os caminhos de escrita.

        `get_asset` sobrescreve `status` com o valor consolidado; como o objeto
        e o mesmo que a sessao acompanha, quem for gravar depois persistiria o
        derivado no banco sem querer. Escrita usa esta; leitura usa aquela.
        """
        asset = await self._repo.get_asset_by_tag(tag)
        if asset is None:
            raise AssetNotFoundError(tag)
        return asset

    async def get_asset(self, tag: str) -> Asset:
        asset = await self._load_asset(tag)
        asset.status = rollup_status(asset, await self._repo.list_points(tag))
        return asset

    async def create_asset(self, payload: AssetIn) -> Asset:
        if await self._repo.get_asset_by_tag(payload.tag) is not None:
            raise AssetAlreadyExistsError(payload.tag)
        return await self._repo.add_asset(Asset(**payload.model_dump()))

    async def update_asset(
        self, tag: str, payload: AssetUpdate, actor: str = "system", role: str = "system"
    ) -> Asset:
        asset = await self._load_asset(tag)
        coords_before = {"x": asset.position_x, "y": asset.position_y}
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(asset, field, value)
        updated = await self._repo.update_asset(asset)

        # Trilha de rastreabilidade da TAG na planta (governanca): registra a
        # edicao/movimentacao com coordenadas antes/depois e hash de integridade.
        coords_after = {"x": updated.position_x, "y": updated.position_y}
        moved = coords_before != coords_after
        await TagAuditRepository(self._repo._session).record(
            action="movimentacao" if moved else "edicao",
            user_id=actor,
            user_role=role,
            tag_id=updated.tag,
            equipment_id=updated.serial_number or updated.model,
            coords_before=coords_before,
            coords_after=coords_after,
            data_origin="humano",
        )
        return updated

    async def validate_asset(self, tag: str, actor: str) -> Asset:
        """Validacao manual de cadastro (perfil Gestor de Planta / Admin).

        Confirma um cadastro gerado por IA: registra quem validou e quando -
        accountability exigida pela governanca (nenhum cadastro 100% automatico
        sem supervisao humana).
        """
        asset = await self._load_asset(tag)
        asset.validated_by = actor
        asset.validated_at = datetime.now(UTC)
        return await self._repo.update_asset(asset)

    async def delete_asset(self, tag: str) -> None:
        await self._repo.delete_asset(await self._load_asset(tag))

    # --------------------- Plants / Areas ----------------------
    async def list_plants(self) -> list[Plant]:
        return await self._repo.list_plants()

    async def create_plant(self, payload: PlantIn) -> Plant:
        return await self._repo.add_plant(Plant(**payload.model_dump()))

    async def list_areas(self) -> list[Area]:
        return await self._repo.list_areas()

    async def create_area(self, payload: AreaIn) -> Area:
        if await self._repo.get_plant(payload.plant_id) is None:
            raise PlantNotFoundError(str(payload.plant_id))
        return await self._repo.add_area(Area(**payload.model_dump()))

    # ----------------------- Busca / hierarquia -----------------------
    async def search_assets(
        self,
        search: str | None,
        status: str | None,
        asset_type: str | None,
        plant_id: UUID | None,
    ) -> list[Asset]:
        return await self._repo.search_assets(search, status, asset_type, plant_id)

    async def get_hierarchy(self) -> list[Plant]:
        plants = await self._repo.list_hierarchy()
        # A arvore so traz equipamentos (o repo filtra os pontos de medicao),
        # entao o status dos pontos precisa vir do banco para o rollup.
        points: dict[str, list[Asset]] = {}
        for point in await self._repo.list_points():
            if point.parent_tag:
                points.setdefault(point.parent_tag, []).append(point)
        for plant in plants:
            for area in plant.areas:
                for asset in area.assets:
                    asset.status = rollup_status(asset, points.get(asset.tag, []))
        return plants
