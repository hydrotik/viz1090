#ifndef STYLE_H
#define STYLE_H

#include "SDL2/SDL.h"
#include <string>


//
// This should go to a full theming class
//
typedef struct Style {
    SDL_Color backgroundColor;

    SDL_Color selectedColor;
    SDL_Color planeColor;
    SDL_Color planeGoneColor;
    SDL_Color trailColor;

    SDL_Color geoColor;
    SDL_Color adminColor;
    SDL_Color coastColor;
    SDL_Color waterColor;
    SDL_Color roadColor;
    SDL_Color airportColor;

    SDL_Color labelColor;
    SDL_Color labelLineColor;    
	SDL_Color subLabelColor;   
    SDL_Color labelBackground;

    SDL_Color scaleBarColor;
    SDL_Color buttonColor;
    SDL_Color buttonBackground;
    SDL_Color buttonOutline;

    SDL_Color clickColor;

	SDL_Color black;
	SDL_Color white;
	SDL_Color red;
	SDL_Color green;
	SDL_Color blue;
	SDL_Color orange;
	SDL_Color grey;
	SDL_Color grey_dark;

    bool setTheme(const std::string &themeName) {
        if(themeName == "classic") {
            applyClassic();
            return true;
        }

        if(themeName == "atc") {
            applyAtc();
            return true;
        }

        if(themeName == "map") {
            applyMap();
            return true;
        }

        if(themeName == "light") {
            applyLight();
            return true;
        }

        return false;
    }

    Style() {
        applyClassic();
    }

private:
    SDL_Color rgb(uint8_t r, uint8_t g, uint8_t b) {
        SDL_Color color = {r, g, b, 255};
        return color;
    }

    void setBaseColors() {
        black = rgb(0,0,0);
        white = rgb(255,255,255);
        red = rgb(255,0,0);
        green = rgb(0,255,0);
        blue = rgb(0,0,255);
        orange = rgb(253,151,31);
        grey = rgb(127,127,127);
        grey_dark = rgb(64,64,64);
    }

    void applyClassic() {
        setBaseColors();

        SDL_Color pink = rgb(249,38,114);
        SDL_Color purple = rgb(85, 0, 255);
        SDL_Color purple_dark = rgb(33, 0, 122);
        SDL_Color grey_light = rgb(196,196,196);
        grey = rgb(127,127,127);
        grey_dark = rgb(64,64,64);

        backgroundColor = black;
        selectedColor = pink;
        planeColor = rgb(0,255,174);
        planeGoneColor = grey;
        trailColor = rgb(0,255,174);
        geoColor = purple_dark;
        adminColor = rgb(42, 28, 112);
        coastColor = rgb(52, 70, 160);
        waterColor = rgb(36, 96, 132);
        roadColor = rgb(145, 112, 192);
        airportColor = purple;
        labelColor = white;
        labelLineColor = grey_dark;
        subLabelColor = grey;
        labelBackground = black;
        scaleBarColor = grey_light;
        buttonColor = grey_light;
        buttonBackground = black;
        buttonOutline = grey_light;
        clickColor = grey;
    }

    void applyAtc() {
        setBaseColors();

        backgroundColor = rgb(0, 6, 4);
        selectedColor = rgb(255, 214, 92);
        planeColor = rgb(0, 255, 157);
        planeGoneColor = rgb(30, 91, 76);
        trailColor = rgb(0, 174, 126);
        geoColor = rgb(0, 93, 72);
        adminColor = rgb(0, 62, 55);
        coastColor = rgb(0, 118, 120);
        waterColor = rgb(0, 68, 88);
        roadColor = rgb(98, 150, 82);
        airportColor = rgb(0, 196, 157);
        labelColor = rgb(198, 255, 233);
        labelLineColor = rgb(31, 117, 93);
        subLabelColor = rgb(104, 176, 151);
        labelBackground = rgb(0, 10, 8);
        scaleBarColor = rgb(75, 166, 137);
        buttonColor = rgb(144, 235, 207);
        buttonBackground = rgb(0, 10, 8);
        buttonOutline = rgb(45, 139, 112);
        clickColor = rgb(0, 255, 157);
    }

    void applyMap() {
        setBaseColors();

        backgroundColor = rgb(8, 14, 18);
        selectedColor = rgb(255, 185, 91);
        planeColor = rgb(76, 224, 255);
        planeGoneColor = rgb(79, 94, 103);
        trailColor = rgb(52, 172, 201);
        geoColor = rgb(66, 93, 103);
        adminColor = rgb(50, 67, 76);
        coastColor = rgb(45, 116, 146);
        waterColor = rgb(28, 71, 102);
        roadColor = rgb(178, 142, 82);
        airportColor = rgb(172, 119, 255);
        labelColor = rgb(222, 233, 236);
        labelLineColor = rgb(81, 100, 107);
        subLabelColor = rgb(145, 161, 166);
        labelBackground = rgb(8, 14, 18);
        scaleBarColor = rgb(175, 190, 193);
        buttonColor = rgb(216, 229, 232);
        buttonBackground = rgb(12, 20, 24);
        buttonOutline = rgb(96, 115, 121);
        clickColor = rgb(76, 224, 255);
    }

    void applyLight() {
        setBaseColors();

        backgroundColor = rgb(232, 238, 238);
        selectedColor = rgb(189, 76, 0);
        planeColor = rgb(0, 82, 104);
        planeGoneColor = rgb(125, 139, 143);
        trailColor = rgb(41, 126, 146);
        geoColor = rgb(118, 140, 145);
        adminColor = rgb(163, 172, 173);
        coastColor = rgb(84, 144, 172);
        waterColor = rgb(119, 179, 204);
        roadColor = rgb(168, 132, 72);
        airportColor = rgb(103, 72, 158);
        labelColor = rgb(15, 27, 31);
        labelLineColor = rgb(96, 115, 121);
        subLabelColor = rgb(64, 82, 88);
        labelBackground = rgb(232, 238, 238);
        scaleBarColor = rgb(45, 63, 68);
        buttonColor = rgb(20, 35, 40);
        buttonBackground = rgb(232, 238, 238);
        buttonOutline = rgb(88, 108, 114);
        clickColor = rgb(0, 82, 104);
    }
} Style;

#endif
