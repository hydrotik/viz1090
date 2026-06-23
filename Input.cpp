// viz1090, a vizualizer for dump1090 ADSB output
//
// Copyright (C) 2020, Nathan Matsuda <info@nathanmatsuda.com>
// Copyright (C) 2014, Malcolm Robb <Support@ATTAvionics.com>
// Copyright (C) 2012, Salvatore Sanfilippo <antirez at gmail dot com>
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are
// met:
//
//  *  Redistributions of source code must retain the above copyright
//     notice, this list of conditions and the following disclaimer.
//
//  *  Redistributions in binary form must reproduce the above copyright
//     notice, this list of conditions and the following disclaimer in the
//     documentation and/or other materials provided with the distribution.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
// A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
// HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
// SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
// LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
// DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
// THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
//

#include "Input.h"

#include <cstdio>
#include <vector>

static std::vector<SDL_GameController *> gameControllers;
static std::vector<SDL_Joystick *> joysticks;
static std::vector<SDL_JoystickID> gameControllerJoystickIds;

static std::chrono::high_resolution_clock::time_point now() {
    return std::chrono::high_resolution_clock::now();
}

// static uint64_t now() {
//     return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::high_resolution_clock::now().time_since_epoch).count();
// }

static uint64_t elapsed(std::chrono::high_resolution_clock::time_point ref) {
	return std::chrono::duration_cast<std::chrono::milliseconds>(now() - ref).count();
}

template <typename T> int sgn(T val) {
    return (T(0) < val) - (val < T(0));
}

static void zoom(View *view, float factor) {
    view->maxDist *= factor;
    if(view->maxDist < 0.001f) {
        view->maxDist = 0.001f;
    }

    view->mapTargetMaxDist = 0;
    view->mapMoved = 1;
    view->highFramerate = true;
}

static void pan(View *view, float dx, float dy) {
    view->moveCenterRelative(dx, dy);
    view->mapTargetLat = 0;
    view->mapTargetLon = 0;
    view->mapTargetMaxDist = 0;
    view->mapMoved = 1;
    view->highFramerate = true;
}

static void panNorth(View *view) {
    pan(view, 0, -0.12f * view->screen_height);
}

static void panSouth(View *view) {
    pan(view, 0, 0.12f * view->screen_height);
}

static void panWest(View *view) {
    pan(view, -0.12f * view->screen_width, 0);
}

static void panEast(View *view) {
    pan(view, 0.12f * view->screen_width, 0);
}

static void recenter(View *view, AppData *appData) {
    view->centerLat = appData->modes.fUserLat;
    view->centerLon = appData->modes.fUserLon;
    view->mapTargetLat = 0;
    view->mapTargetLon = 0;
    view->mapTargetMaxDist = 0;
    view->mapMoved = 1;
    view->highFramerate = true;
}

static void handleControllerButton(Input *input, int button) {
    switch(button) {
        case SDL_CONTROLLER_BUTTON_DPAD_UP:
            panNorth(input->view);
        break;

        case SDL_CONTROLLER_BUTTON_DPAD_DOWN:
            panSouth(input->view);
        break;

        case SDL_CONTROLLER_BUTTON_DPAD_LEFT:
            panWest(input->view);
        break;

        case SDL_CONTROLLER_BUTTON_DPAD_RIGHT:
            panEast(input->view);
        break;

        case SDL_CONTROLLER_BUTTON_RIGHTSHOULDER:
        case SDL_CONTROLLER_BUTTON_X:
            zoom(input->view, 0.5f);
        break;

        case SDL_CONTROLLER_BUTTON_LEFTSHOULDER:
        case SDL_CONTROLLER_BUTTON_Y:
            zoom(input->view, 1.5f);
        break;

        case SDL_CONTROLLER_BUTTON_A:
            recenter(input->view, input->appData);
        break;

        case SDL_CONTROLLER_BUTTON_B:
            input->view->toggleLightMode();
        break;

        default:
        break;
    }
}

static void handleJoystickButton(Input *input, int button) {
    switch(button) {
        case 0:
            zoom(input->view, 0.5f);
        break;

        case 1:
            recenter(input->view, input->appData);
        break;

        case 2:
            input->view->toggleLightMode();
        break;

        case 3:
            zoom(input->view, 1.5f);
        break;

        case 4:
            zoom(input->view, 1.5f);
        break;

        case 5:
            zoom(input->view, 0.5f);
        break;

        default:
        break;
    }
}

static void handleJoystickHat(Input *input, Uint8 value) {
    if(value & SDL_HAT_UP) {
        panNorth(input->view);
    }

    if(value & SDL_HAT_DOWN) {
        panSouth(input->view);
    }

    if(value & SDL_HAT_LEFT) {
        panWest(input->view);
    }

    if(value & SDL_HAT_RIGHT) {
        panEast(input->view);
    }
}

static bool joystickInstanceIsGameController(SDL_JoystickID instanceId) {
    for(std::vector<SDL_JoystickID>::iterator id = gameControllerJoystickIds.begin(); id != gameControllerJoystickIds.end(); ++id) {
        if(*id == instanceId) {
            return true;
        }
    }

    return false;
}

static bool isUConsoleShoulderMouseEvent(const SDL_MouseButtonEvent *button) {
    return button->which == 0 && button->x == 0 && button->y == 0 &&
        (button->button == SDL_BUTTON_LEFT || button->button == SDL_BUTTON_RIGHT);
}

static void handleUConsoleShoulderMouseEvent(Input *input, const SDL_MouseButtonEvent *button) {
    if(button->button == SDL_BUTTON_LEFT) {
        zoom(input->view, 1.5f);
    } else if(button->button == SDL_BUTTON_RIGHT) {
        zoom(input->view, 0.5f);
    }
}

void Input::getInput()
{
	SDL_Event event;
		
	while (SDL_PollEvent(&event))
	{
		switch (event.type)
		{
			case SDL_QUIT:
				exit(0);
			break;
			
			case SDL_KEYDOWN:
                if(debugInput) {
                    printf("input key sym=%s scancode=%s mod=%u repeat=%u\n",
                        SDL_GetKeyName(event.key.keysym.sym),
                        SDL_GetScancodeName(event.key.keysym.scancode),
                        event.key.keysym.mod,
                        event.key.repeat);
                }

				switch (event.key.keysym.sym)
				{
					case SDLK_ESCAPE:
						exit(0);
					break;

                    case SDLK_UP:
                    case SDLK_w:
                    case SDLK_k:
                        panNorth(view);
                    break;

                    case SDLK_DOWN:
                    case SDLK_s:
                    case SDLK_j:
                        panSouth(view);
                    break;

                    case SDLK_LEFT:
                    case SDLK_a:
                    case SDLK_h:
                        panWest(view);
                    break;

                    case SDLK_RIGHT:
                    case SDLK_d:
                    case SDLK_l:
                        panEast(view);
                    break;

                    case SDLK_HOME:
                    case SDLK_r:
                        recenter(view, appData);
                    break;

                    case SDLK_t:
                        view->toggleLightMode();
                    break;

					case SDLK_MINUS:
                    case SDLK_KP_MINUS:
                    case SDLK_PAGEDOWN:
                        zoom(view, 1.5f);
    				break;

    				case SDLK_EQUALS:
                    case SDLK_PLUS:
                    case SDLK_KP_PLUS:
                    case SDLK_PAGEUP:
                        zoom(view, 0.5f);
    				break;

					default:
					break;
				}

			break;

            case SDL_CONTROLLERBUTTONDOWN:
                if(debugInput) {
                    printf("input controller button=%s index=%d\n",
                        SDL_GameControllerGetStringForButton(static_cast<SDL_GameControllerButton>(event.cbutton.button)),
                        event.cbutton.button);
                }

                handleControllerButton(this, event.cbutton.button);
            break;

            case SDL_JOYBUTTONDOWN:
                if(joystickInstanceIsGameController(event.jbutton.which)) {
                    break;
                }

                if(debugInput) {
                    printf("input joystick button joy=%d button=%d\n", static_cast<int>(event.jbutton.which), event.jbutton.button);
                }

                handleJoystickButton(this, event.jbutton.button);
            break;

            case SDL_JOYHATMOTION:
                if(joystickInstanceIsGameController(event.jhat.which)) {
                    break;
                }

                if(debugInput) {
                    printf("input joystick hat joy=%d hat=%d value=%u\n", static_cast<int>(event.jhat.which), event.jhat.hat, event.jhat.value);
                }

                handleJoystickHat(this, event.jhat.value);
            break;

			case SDL_MOUSEWHEEL:
                if(debugInput) {
                    printf("input mouse wheel x=%d y=%d direction=%u\n", event.wheel.x, event.wheel.y, event.wheel.direction);
                }

				zoom(view, 1.0 + 0.5 * sgn(event.wheel.y));
				break;

			case SDL_MULTIGESTURE:
				view->maxDist /=1.0 + 4.0*event.mgesture.dDist;
				view->mapTargetMaxDist = 0;
				view->mapMoved = 1;

				if(elapsed(touchDownTime) > 100) {
						//touchDownTime = 0;
				}
				break;

			case SDL_FINGERMOTION:;	
				if(elapsed(touchDownTime) > 150) {
					tapCount = 0;
					//touchDownTime = 0;
				}		
				view->moveCenterRelative( view->screen_width * event.tfinger.dx,  view->screen_height * event.tfinger.dy);
				break;

			case SDL_FINGERDOWN:
				if(elapsed(touchDownTime) > 500) {
					tapCount = 0;
				} 


				//this finger number is always 1 for down and 0 for up an rpi+hyperpixel??
				if(SDL_GetNumTouchFingers(event.tfinger.touchId) <= 1) {
					touchDownTime = now();	
				}
				break;

			case SDL_FINGERUP:
				if(elapsed(touchDownTime) < 150 && SDL_GetNumTouchFingers(event.tfinger.touchId) == 0) {
					touchx = view->screen_width * event.tfinger.x;
					touchy = view->screen_height * event.tfinger.y;
					tapCount++;
					view->registerClick(tapCount, touchx, touchy);
				} else {
					touchx = 0;
					touchy = 0;
					tapCount = 0;
				}

				break;

			case SDL_MOUSEBUTTONDOWN:
                if(debugInput) {
                    printf("input mouse down which=%u button=%u clicks=%u x=%d y=%d\n",
                        event.button.which,
                        event.button.button,
                        event.button.clicks,
                        event.button.x,
                        event.button.y);
                }

				if(event.button.which != SDL_TOUCH_MOUSEID) {
                    if(isUConsoleShoulderMouseEvent(&event.button)) {
                        break;
                    }

					if(elapsed(touchDownTime) > 500) {
						tapCount = 0;
					}
					touchDownTime = now();
				}
				break;

			case SDL_MOUSEBUTTONUP:;
                if(debugInput) {
                    printf("input mouse up which=%u button=%u clicks=%u x=%d y=%d\n",
                        event.button.which,
                        event.button.button,
                        event.button.clicks,
                        event.button.x,
                        event.button.y);
                }

				if(event.button.which != SDL_TOUCH_MOUSEID) {
                    if(isUConsoleShoulderMouseEvent(&event.button)) {
                        handleUConsoleShoulderMouseEvent(this, &event.button);
                        break;
                    }

					touchx = event.button.x;
					touchy = event.button.y;
					tapCount = event.button.clicks;

					view->registerClick(tapCount, touchx, touchy);
				}
				break;

			case SDL_MOUSEMOTION:;

				if(event.motion.which != SDL_TOUCH_MOUSEID) {
					view->registerMouseMove(event.motion.x, event.motion.y);
					
					if (SDL_GetMouseState(NULL, NULL) & SDL_BUTTON(SDL_BUTTON_LEFT)) {
						view->moveCenterRelative(event.motion.xrel, event.motion.yrel);
					}					
				}
				break;				
		}
	}
}

Input::Input(AppData *appData, View *view) {
	this->view = view;
	this->appData = appData;
    this->debugInput = false;

    SDL_GameControllerEventState(SDL_ENABLE);
    SDL_JoystickEventState(SDL_ENABLE);

    int joystickCount = SDL_NumJoysticks();
    for(int i = 0; i < joystickCount; i++) {
        if(SDL_IsGameController(i)) {
            SDL_GameController *controller = SDL_GameControllerOpen(i);
            if(controller) {
                gameControllers.push_back(controller);
                SDL_Joystick *joystick = SDL_GameControllerGetJoystick(controller);
                if(joystick) {
                    gameControllerJoystickIds.push_back(SDL_JoystickInstanceID(joystick));
                }
            }
        } else {
            SDL_Joystick *joystick = SDL_JoystickOpen(i);
            if(joystick) {
                joysticks.push_back(joystick);
            }
        }
    }
}


