# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog],
and this project adheres to [Semantic Versioning].

## [0.1.4] - 2025-07-10

### Changed

Fix compatibility with frozen dataclasses for Home Assistant 2024.x

- Refactor entity descriptions to use dataclasses.replace instead of direct attribute assignment
- Prevent FrozenInstanceError on Sensor and BinarySensor entities
- Clean up legacy code and ensure compatibility with latest Home Assistant core

## [0.1.3] - 2023-04-20

### Changed

- Improved handling of rain sensor.
