pureSxS
=======
A tool to export Component Based Servicing packages from a full Windows installation.

Usage
-----
```
pureSxS.py <source_mum> <destination>
```

pureSxS takes two arguments: a source manifest and a destination directory. The source manifest's directory should contain every dependency of the source manifest package from the following directories merged together:
 * Windows\Servicing\Packages
 * Windows\WinSxS
 * Windows\WinSxS\Manifests

All missing dependencies will be logged as **warnings** during the process.

The destination will be populated with packages and dependencies related to, and including, the source manifest. If desired, the tool may be run multiple times with the same destination to append more packages and dependencies.

You can also use this tool to export single packages from UUP packages by simply extracting them to directory and running this tool.

### Example usage
```
pureSxS.py "source\Microsoft-Windows-ProfessionalEdition~31bf3856ad364e35~amd64~~10.0.19041.1.mum" Professional
```
This will export the Professional edition package along with its dependencies.

Acknowledgements
----------------
This tool incorporates [haveSxS](https://github.com/Gamers-Against-Weed/haveSxS) to generate SxS pseudo keys.

License
-------
The project is licensed under the terms of the GNU General Public License v3.0
