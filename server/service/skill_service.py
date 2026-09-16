from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SkillDescriptor:
    name: str
    description: str = ""
    path: Path | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    enabled: bool = True


class SkillService:
    """Skill 服务提供skill的增删查
    """

    def __init__(self) -> None:
        self._skills: dict[str, SkillDescriptor] = {}

    def register_skill(self, skill: SkillDescriptor) -> None:
        self._skills[skill.name] = skill

    def get_skill(self, name: str) -> SkillDescriptor | None:
        return self._skills.get(name)

    def list_skills(self, *, enabled_only: bool = True) -> list[SkillDescriptor]:
        skills = self._skills.values()
        if enabled_only:
            skills = [skill for skill in skills if skill.enabled]
        return sorted(skills, key=lambda skill: skill.name)
