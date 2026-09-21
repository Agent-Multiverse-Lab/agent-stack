import unittest
from pathlib import Path
from unittest.mock import patch

from deepagents.backends import FilesystemBackend

from src.agents.backends.composite_backend import (
    ROUTE_MEMORY,
    ROUTE_SKILL,
    ROUTE_WORKSPACE,
    create_composite_backend,
    create_custom_filesystem_middleware,
)
from src.agents.base_context import BaseContext


class CompositeBackendTest(unittest.TestCase):
    def test_filesystem_middleware_reuses_all_virtual_routes(self):
        context = BaseContext(uid="user-1", thread_id="thread-1")
        memory_backend = FilesystemBackend(
            root_dir=str(Path(__file__).parent.resolve()),
            virtual_mode=True,
        )
        with patch(
            "src.agents.backends.composite_backend.UserMemoriesBackend",
            return_value=memory_backend,
        ):
            backend = create_composite_backend(context)

            middleware = create_custom_filesystem_middleware(
                context=context,
                backend=backend,
            )

            self.assertIs(middleware.backend, backend)
            self.assertEqual(
                set(backend.routes),
                {ROUTE_SKILL, ROUTE_MEMORY, ROUTE_WORKSPACE},
            )


if __name__ == "__main__":
    unittest.main()
