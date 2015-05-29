# Helping

[![Join the chat at https://gitter.im/fieldpapers/fieldpapers](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/fieldpapers/fieldpapers?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

So, you want to help with Field Papers. Great!

Field Papers is fundamentally about facilitating the production of printed
(web) maps and providing a means to capture data that has been collected in the
field.

In its current form, this translates to the creation of multi-page PDFs
(intended for varying paper sizes), ideally at high resolution, using map
sources and overlays that follow [Slippy
Map](http://wiki.openstreetmap.org/wiki/Slippy_Map) file naming conventions.
Furthermore, each page includes a QR code with a link to a page that describes
the content of that page (in both human- and computer-readable forms).

The existence of quick, purpose-built paper maps that can be annotated is often
sufficient, but FP goes a step further and will take the offline online.

Pages may be turned into snapshots by scanning them or taking photos and then
uploading them. These images will be geo-rectified and turned into a slippy map
layer suitable for browsing or as an overlay in a tool like QGIS, iD, or JOSM.
(They're also available for download as GeoTIFFs.)

That's basically it. Obviously additional features / tweaks complete the
picture, which is where you come in.

## Project Breakdown

* The live site: [fieldpapers.org](http://fieldpapers.org/)
* [The translation project on Transifex](https://www.transifex.com/projects/p/fieldpapers/)
* [fp-web](https://github.com/fieldpapers/fp-web) - the updated website (Ruby/Rails)
* [fp-scanner](https://github.com/fieldpapers/fp-scanner) - the updated scanning / rectification tools (EXPERIMENTAL)
* [fp-printer](https://github.com/fieldpapers/fp-printer) - the updated atlas-creation pipeline (EXPERIMENTAL)
* [fp-legacy](https://github.com/fieldpapers/fp-legacy) - the existing site, scanning, and atlas creation pipelines
* [fieldpapers](https://github.com/fieldpapers/fieldpapers) - the umbrella project, for tracking issues, etc.
* [fp-tiler](https://github.com/fieldpapers/fp-tiler) - the tile server.
* [tilelive-fieldpapers](https://github.com/fieldpapers/tilelive-fieldpapers) - the tilelive module that drives the tile server.
* [fp-tasks](https://github.com/fieldpapers/fp-tasks) - the task server, which provides a web API on top of the printing and snapshot processing components of fp-legacy.

## For Multi-lingual Individuals

Field Papers is often used on the ground in disaster-stricken areas and the
developing world, and not everyone speaks English. Field Papers is intended to
be translated, so please help! We have a [Field Papers project on
Transifex](https://www.transifex.com/projects/p/fieldpapers/) that you can
contribute to. Even partial translations are better than none, so let's get
started!

Web site translation status:

[![Translation Status (www)](https://www.transifex.com/projects/p/fieldpapers/resource/www/chart/image_png)](https://www.transifex.com/projects/p/fieldpapers/resource/www/)

Field Papers uses [Devise](https://github.com/plataformatec/devise) for
managing users. As a result, we can share translations with other projects.
Translations are managed using [Locale](https://www.localeapp.com/):
[devise-i18n](https://www.localeapp.com/projects/377)
([GH](https://github.com/tigrish/devise-i18n)),
[devise-i18n-views](https://www.localeapp.com/projects/2263)
([GH](https://github.com/mcasimir/devise-i18n-views)).

If you encounter strings on the site that don't appear to have corresponding
entries in Transifex or Locale, please [open an
issue](https://github.com/fieldpapers/fieldpapers/issues/new) so we can track
them down.

## For Web Developers

The Field Papers web site is a standard Rails application, chosen to minimize
the amount of effort required to implement standard features (Rails has
a fantastic ecosystem of plugins for concerns ranging from pagination to user
account management). The front-end is similarly intended to be simple, with the
majority of effort spent on configuring and extended
[Leaflet](http://leafletjs.com/) for our purposes.

Have a look at the [issue list](https://github.com/fieldpapers/fieldpapers/issues)
and see if there are things that appeal or seem doable. If there's insufficient
information, ask for more!

## For Designers

Field Papers' current design represents its minimalist past. While we intend to
keep it simple (especially for users on low-bandwidth connections), that
doesn't mean we can't add a bit of flair. The same goes for the design of the
printed atlases--they originally used Python (and Cairo) to produce PDFs, but
are now using HTML, which expands our options.

## For Computer Vision Enthusiasts

The [scanner component](https://github.com/fieldpapers/fp-scanner) uses OpenCV
to extract and geo-reference maps from images. There's surely more we can do to
digitize field annotations!

## For Ops People

We haven't tackled instrumentation and monitoring yet and we're not totally
clear on how we're going to deploy (Heroku is a reasonable default, and we're
aiming to provide `Dockerfile`s for each component). Weigh in with your
expertise and help us figure out the best approach.

Field Papers isn't just fieldpapers.org, as some organizations have configured
it in "appliance-mode" before deploying it into the field. Let's do what we can
to keep this process smooth.

## For Everyone Else

If you're using Field Papers, we care about how you're using it. If you're
finding bugs, [let us
know](https://github.com/fieldpapers/fieldpapers/issues/new) and help us fix
them. If you have ideas about features that would make your life easier, write
them up as proposals (explaining _how_ they would be useful, particularly in
the field, is very helpful) and add them either as GitHub issues or on the wiki
(we're still figuring this out) and see what you can do to drum up feedback and
support.

Documentation in its many forms is also immensely welcomed, whether it's how to
use Field Papers with QGIS or collections of good ways to use it in your local
community.
