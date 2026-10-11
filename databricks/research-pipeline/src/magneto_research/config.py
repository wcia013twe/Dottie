"""Non-secret references, independent of the live director's configuration."""
from dataclasses import dataclass
import re
import tomllib
from urllib.parse import urlparse


@dataclass(frozen=True)
class ResearchConfig:
    workspace_host: str
    catalog: str
    schema: str
    source_volume: str
    experiment_name: str | None = None
    search_index: str | None = None
    warehouse_id: str | None = None
    search_endpoint: str | None = None
    embedding_endpoint: str | None = None
    judge_model: str | None = None
    table_prefix: str = 'research'

    def __post_init__(self):
        host = urlparse(self.workspace_host)
        if (host.scheme != 'https' or not host.hostname or host.username or host.password
                or host.path not in ('', '/') or host.query or host.fragment):
            raise ValueError('workspace_host must be an HTTPS origin')
        names = [self.catalog, self.schema, self.source_volume, self.table_prefix]
        if self.search_index is not None:
            parts = self.search_index.split('.')
            if len(parts) != 3:
                raise ValueError('search_index must be catalog.schema.index')
            names.extend(parts)
        if any(not re.fullmatch(r'[a-z][a-z0-9_]*', name) for name in names):
            raise ValueError('Resource names must be simple lowercase identifiers')
        if self.experiment_name is not None and not self.experiment_name.startswith('/'):
            raise ValueError('experiment_name must be an absolute workspace path')
        if self.experiment_name and ('director' in self.experiment_name.lower()
                                     or 'agentbricks_traces' in self.experiment_name.lower()):
            raise ValueError('Use a separate research experiment')
        if self.search_index and not self.search_index.startswith(self.schema_name + '.'):
            raise ValueError('Research index must use the configured schema')

    def table(self, suffix):
        if suffix not in {'sources', 'chunks', 'findings', 'recommendations', 'reviews',
                          'runs', 'search_documents', 'latest_reviews', 'eligible_chunks',
                          'eligible_findings', 'eligible_recommendations', 'eligible_documents'}:
            raise ValueError('Unknown research table')
        return f'{self.schema_name}.{self.table_prefix}_{suffix}'

    @property
    def volume_path(self):
        return f'/Volumes/{self.catalog}/{self.schema}/{self.source_volume}/research'

    @classmethod
    def load(cls, path):
        with open(path, 'rb') as source:
            return cls(**tomllib.load(source))

    @property
    def schema_name(self):
        return f'{self.catalog}.{self.schema}'

    @property
    def volume_name(self):
        return f'{self.schema_name}.{self.source_volume}'
