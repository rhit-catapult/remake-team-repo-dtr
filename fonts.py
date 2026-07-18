"""Shared fonts. Importing this initializes pygame's font system so any module
can render text without depending on the main module."""
import pygame

pygame.font.init()

HEALTH_FONT = pygame.font.SysFont("Pixel Code", 24)
DEATH_FONT_BIG = pygame.font.SysFont("Pixel Code", 84, bold=True)
DEATH_FONT_MED = pygame.font.SysFont("Pixel Code", 34)
