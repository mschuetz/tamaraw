"use strict";
var Tamaraw = {
/**
 * @param selector
 * @param aspect_ratio the aspect ratio of the image(s). as in 1.33 is 4:3
 * the approximate amount of screen real estate it is supposed to take
 *
 * assumes the image src uri ends with "_WIDTHxHEIGHT".
 */
resize_images: function(selector, aspect_ratio, width_real_estate) {
    function parse_dimensions(img_source) {
        var matches = img_source.match(/_(\d+)x(\d+)$/)
        if (matches == null) {
            throw new Exception("could not parse image dimensions");
        }
        return [parseInt(matches[1]), parseInt(matches[2])];
    }

    var current_image_width = parse_dimensions($(selector)[0].src);

    function window_width() {
        var ratio = window.devicePixelRatio;
        if ($.isNumeric(ratio) && ratio > 1) {
            console.log("detected hidpi display with ratio=" + ratio);
            return $(window).width() * ratio;
        }
        return $(window).width();
    }

    function do_resize() {
        console.log('in resize selector=' + selector);
        var new_width = Math.ceil(window_width() * width_real_estate / 300) * 320;
        if (new_width == current_image_width) {
            return;
        }
        console.log('new_width=' + new_width);
        current_image_width = new_width;
        var new_height = Math.ceil(new_width / aspect_ratio);

        $(selector).each(function(_, img) {
            img.src = img.src.replace(/_\d+x\d+$/, '_' + new_width + 'x' + new_height)
        });
    }
    $(window).resize(do_resize);
    do_resize();
}
};
