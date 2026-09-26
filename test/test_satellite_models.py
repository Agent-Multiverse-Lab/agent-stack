import unittest

from sqlalchemy.orm import configure_mappers

from src.database import (
    Base,
    SatelliteBusinessScene,
    SatelliteCollection,
    SatelliteScene,
    SatelliteSceneAsset,
    SatelliteSource,
)


class SatelliteModelMappingTest(unittest.TestCase):
    def test_all_catalog_tables_are_registered(self) -> None:
        configure_mappers()
        self.assertEqual(
            {
                model.__tablename__
                for model in (
                    SatelliteSource,
                    SatelliteCollection,
                    SatelliteScene,
                    SatelliteSceneAsset,
                    SatelliteBusinessScene,
                )
            },
            {
                "satellite_sources",
                "satellite_collections",
                "satellite_scenes",
                "satellite_scene_assets",
                "satellite_business_scenes",
            },
        )
        self.assertTrue(set(model.__tablename__ for model in (
            SatelliteSource, SatelliteCollection, SatelliteScene,
            SatelliteSceneAsset, SatelliteBusinessScene,
        )).issubset(Base.metadata.tables))

    def test_scene_and_asset_keys_match_migrations(self) -> None:
        scene = SatelliteScene.__table__
        assets = SatelliteSceneAsset.__table__
        business = SatelliteBusinessScene.__table__

        self.assertEqual(scene.c.footprint.type.get_col_spec(), "geometry(Polygon,4326)")
        self.assertEqual(
            {column.name for column in business.primary_key.columns},
            {"scene_id", "business_code"},
        )
        self.assertEqual(
            {column.name for column in assets.constraints
             if column.name == "uq_satellite_scene_assets_scene_asset_key"},
            {"uq_satellite_scene_assets_scene_asset_key"},
        )
        self.assertIn("metadata", assets.c)


if __name__ == "__main__":
    unittest.main()
