pureSxS
=======
A tool to export Component Based Servicing packages from a full Windows installation.

Usage
-----
```
pureSxS.py <source_mum> <destination>
```

pureSxS works on a specified directory to export packages. Simply place the contents of the following directories into one:
 * Windows\Servicing\Packages
 * Windows\WinSxS
 * Windows\WinSxS\Manifests

You can also use this tool to export single packages from UUP packages by simply extracting them to directory and running this tool.

### Example usage
```
pureSxS.py "source\Microsoft-Windows-ProfessionalEdition~31bf3856ad364e35~amd64~~10.0.19041.1.mum" Professional
```
This will export the Professional edition package along with its dependencies.

Acknowledgements
----------------
This tool incorporates a modified version of [haveSxS](https://github.com/Gamers-Against-Weed/haveSxS) to generate SxS pseudo keys.

License
-------
The project is licensed under the terms of the GNU General Public License v3.0
