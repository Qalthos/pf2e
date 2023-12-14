#!/usr/bin/env python
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib
from typing import Self

import yaml


@dataclass
class Save:
    type: str
    basic: bool = False
    success: str = ""
    failure: str = ""
    critical: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Self:
        return cls(**data)

    def __str__(self) -> str:
        save_desc = f"Creatures within the area of effect must make a {'basic ' if self.basic else ''}{self.type} save.\n"
        if self.success:
            save_desc += f"  Success: The target is {self.success}.\n"
        if self.failure:
            save_desc += f"  Failure: The target is {self.failure}.\n"
        if self.critical:
            save_desc += f"  Critical Failure: The target is {self.critical}.\n"
        return save_desc


@dataclass
class Variant:
    level: str
    bonus: int = 0
    damage: int|str = 0
    splash: int = 0
    persistent: int|str = 0

    @classmethod
    def from_dict(cls, data: dict[str, int|str]) -> Self:
        return cls(**data)

    @property
    def avg_dmg(self) -> float:
        total = self.splash
        if isinstance(self.damage, int):
            total += self.damage
        else:
            count, damage = self.damage.split("d")
            total += int(count) * int(damage) / 2
        # Persistent has an expected 3.24x effect
        if isinstance(self.persistent, int):
            persist = (self.persistent + self.splash)
        else:
            count, damage = self.persistent.split("d")
            persist = int(count) * int(damage) / 2
        # Sticky bomb
        # total += (persist + self.splash) * 3.24
        total = persist * 3.24

        return total


@dataclass
class Bomb:
    type: str
    levels: dict[int, Variant]
    on_hit: str = ""
    on_crit: str = ""
    additional: str = ""
    save: Save|None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        levels = data.pop("levels")
        variants = {k: Variant.from_dict(v) for k,v in levels.items()}

        save = None
        if "save" in data:
            save = Save.from_dict(data.pop("save"))

        return cls(**data, levels=variants, save=save)

    def variant_str(self, level: int) -> str:
        variant = self.levels[level]
        description = []

        # Save
        save = ""
        if self.save:
            save = str(self.save)


        # Attack bonus
        if bonus := variant.bonus:
            description.append(f"You gain a +{bonus} bonus to attack rolls")

        # Damage
        damages = []
        damage_type = self.type
        if damage := variant.damage:
            damages.append(f"{damage} {damage_type} damage")
        if persistent := variant.persistent:
            damages.append(f"{persistent} persistent {damage_type} damage")
        if splash := variant.splash:
            damages.append(f"{splash} {damage_type} splash damage")
        if additional := self.additional:
            damages.append(f"{damage} additional {additional} damage")
        if damages:
            description.append(f"The bomb deals {', '.join(damages)}")

        # Side effects
        if effect := self.on_hit:
            description.append(f"On a hit, the target is {effect} until the start of your next turn")
        if effect := self.on_crit:
            description.append(f"On a critical hit, the target is {effect} until the start of your next turn")

        return  save + ". ".join(description) + "."

    def match(self, search: list[str]) -> bool:
        match = True
        for item in search:
            negate = False
            if item[0] == "-":
                item = item[1:]
                negate = True

            check = any((
                item in self.type,
                item in self.on_hit,
                item in self.on_crit,
                item in self.additional,
                all((
                    self.save,
                    item in str(self.save),
                ))
            ))
            if negate:
                match = match and not check
            else:
                match = match and check
            if not match:
                return False
        return match


def read_config() -> dict[str, Any]:
    config = Path("config.toml")
    with config.open("rb") as config_file:
        toml = tomllib.load(config_file)
    return toml


def read_formulae() -> list[str]:
    formula_book = Path("formula_book")
    lines: list[str] = []
    with formula_book.open("r") as formulas:
        lines = formulas.read().splitlines()

    return [line for line in lines if line[0] != "#"]


def read_bombs() -> dict[str, Bomb]:
    bombs = Path("data/bombs.yaml")
    with bombs.open("r") as bomb_file:
        data = yaml.load(bomb_file, Loader=yaml.CLoader)
    for bomb in data:
        data[bomb] = Bomb.from_dict(data[bomb])
    return data


def parse_bomb(name: str, bomb: Bomb, level: int) -> str:
    variant = bomb.levels[level]
    full_name = f"{name.title()} ({variant.level.title()}) [{level}] ({variant.avg_dmg} dmg)"
    return f"{full_name}\n{bomb.variant_str(level)}\n"


def main() -> None:
    config = read_config()
    formulae = read_formulae()
    bombs = read_bombs()

    try:
        search = sys.argv[1:]
    except IndexError:
        search = []

    variants: list[tuple[str, Bomb, int]] = []
    for bomb in bombs:
        if search and not bombs[bomb].match(search):
            continue
        if bomb not in formulae:
            print(bomb)
            continue
        levels = bombs[bomb].levels
        version = 0
        for level in levels:
            if level > config["level"]:
                break
            version = level
        if version:
            variants.append((bomb, bombs[bomb], version))

    for name, bomb, level in sorted(variants, key=lambda x: x[1].levels[x[2]].avg_dmg, reverse=True):
        print(parse_bomb(name, bomb, level))


if __name__ == "__main__":
    main()
