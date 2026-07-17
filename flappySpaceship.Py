import pygame
import sys

pygame.init()

SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("My First Pygame Game")

# 3. Set up the game clock (controls frame rate)
clock = pygame.time.Clock()
FPS = 60
xVelo = 50

# Main Game Loop
running = True
while running:

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # 5. Game Logic Updates go here

    # 6. Drawing / Rendering
    screen.fill((40, 44, 52))  # Wipes the screen with a dark gray color

    # (Draw your game characters and shapes here!)

    pygame.display.flip()  # Update the full display Surface to the screen

    # 7. Maintain frame rate
    clock.tick(FPS)


pygame.quit()
sys.exit()


