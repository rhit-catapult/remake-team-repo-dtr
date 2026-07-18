import pygame
import sys
import random


from astroid import Astroid
pygame.init()

SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("astroid bird")
spaceship = pygame.image.load("spaceship.png").convert_alpha()
w, h = spaceship.get_size()
spaceship = pygame.transform.scale(spaceship, (w // 20, h // 20))   # half of its own size
font = pygame.font.SysFont("PIXY", 48)  # Pixel Code font, size 48


# 3. Set up the game clock (controls frame rate)
highscore = 0
clock = pygame.time.Clock()
counter = 0
score = 0
FPS = 60
yVelo = 0
start = False
gameEnd = False

y = 180
l = 20
spawn = False

# Main Game Loop
running = True
astroids = []
while running:
    pressed = pygame.key.get_pressed()
    
        
    if pressed[pygame.K_UP]:
        if spawn == False:
            spawn = True
        yVelo -= 0.5
    if pressed[pygame.K_DOWN]:
        if spawn == False:
            spawn = True
        yVelo += 0.5
    if pressed[pygame.K_r]:
        gameEnd = False
        score = 0
        astroids.clear()
        y = 180
        
    if not gameEnd:
        y += yVelo
    else:
        y += 9.8 
    if (y) >= 440-l:
        y = 440-l
        yVelo *= -0.7
        
    if (y) < 0:
        y = 0
        yVelo *= -0.7
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.fill((40, 44, 52))  # Wipes the screen with a dark gray color

    if not spawn:
            text = font.render("Start: Press Up or Down", True, (255, 255, 255))
    elif score == 10:
            text = font.render("10 pts! Speed Increased", True, (255, 255, 255))
    elif score == 20:
            text = font.render("20 pts! Speed Increased", True, (255, 255, 255))
    else:
            text = font.render(f"{round(score)}", True, (255, 255, 255))

    gameoverText = font.render("Game Over", True, (255, 255, 255))
    scoreText = font.render(f"Score: {round(score)}", True, (255, 255, 255))

    if not gameEnd:
        text_rect = text.get_rect(center = (320,420))
        screen.blit(text,text_rect)
    else:
        highscoreText = font.render(f"highscore: {round(highscore)}", True, (255, 255, 255))
        highscore_rect = highscoreText.get_rect(center = (320,50))
        screen.blit(highscoreText,highscore_rect)
        text = font.render("Restart: Press R", True, (255, 255, 255))
        text_rect = text.get_rect(center = (320,420))
        screen.blit(text,text_rect)
        gameover_rect = gameoverText.get_rect(center = (320,160))
        screen.blit(gameoverText,gameover_rect)
        scoreText_rect = scoreText.get_rect(center = (320,220))
        screen.blit(scoreText,scoreText_rect)
        
    screen.blit(spaceship, (270, y))     # top-left corner goes at (x, y)
    ship_rect = spaceship.get_rect(topleft=(270, y))
    ship_rect.height-=2.5
    ship_rect.width-=5
    if counter % 150 == 0 and spawn and not gameEnd:
        astroids.append(Astroid(700, random.randint((int)(100 + max((100 - 0.025*counter),0)),(int)(150 + max((100-0.01*counter),0)))))

    if not gameEnd:
        for ast in astroids:
            if(score >= 10):
                ast.velo = 2.5
            if(score >= 20):
                ast.velo = 3
            ast.update(screen)
            if ast.x < 260 and ast.point and not gameEnd:
                score += 1
                if score > highscore:
                    highscore = score
                ast.point = False
            if ship_rect.colliderect(ast.lowerRectangle) or ship_rect.colliderect(ast.upperRectangle):
                gameEnd = True


    astroids = [ast for ast in astroids if ast.x > -100]
        
    
    pygame.display.flip()  # Update the full display Surface to the screen

    # 7. Maintain frame rate
    if not gameEnd:
        counter += 1
    clock.tick(FPS)


pygame.quit()
sys.exit()


