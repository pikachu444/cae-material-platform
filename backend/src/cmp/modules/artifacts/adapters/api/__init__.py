"""Protected upload, Raw Asset, and immutable Artifact HTTP resources."""

from cmp.modules.artifacts.adapters.api.content import install_content_artifact_api
from cmp.modules.artifacts.adapters.api.uploads import install_upload_api

__all__ = ["install_content_artifact_api", "install_upload_api"]
