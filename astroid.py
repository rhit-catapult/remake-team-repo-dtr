import sys
import pygame
import random

class Astroid:
    def __init__(self, x, gap):
        self.velo = 2
        self.point = True
        self.x = x
        self.gap = gap
        self.upperGap = random.randint(0, 480 - self.gap)
        self.lowergap = self.upperGap + self.gap
        self.lowerRectangle = pygame.Rect(self.x, 0, 50, 480-self.lowergap)
        self.lowerRectangle.bottom = 480
        self.upperRectangle = pygame.Rect(self.x, 0, 50, self.upperGap)
        self.upperRectangle.top = 0


    def update(self, screen):
        self.x -= self.velo
        
        self.lowerRectangle = pygame.Rect(self.x, 0, 50, 480-self.lowergap)
        self.lowerRectangle.bottom = 480
        self.upperRectangle = pygame.Rect(self.x, 0, 50, self.upperGap)
        self.upperRectangle.top = 0
        
        pygame.draw.rect(screen, (255, 255, 255), self.lowerRectangle)
        pygame.draw.rect(screen, (255, 255, 255), self.upperRectangle)
        
    

        
