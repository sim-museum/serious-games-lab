# copy game files created in the last 2 hours to afterGamesReport
find . -name "*.sgf" -type f -mmin -120 -not -path "./afterGamesReport/*" -exec cp {} ./afterGamesReport \;
find . -name "*.rsgf" -type f -mmin -120 -not -path "./afterGamesReport/*" -exec cp {} ./afterGamesReport \;
find . -name "*.rsgf.csv" -type f -mmin -120 -not -path "./afterGamesReport/*" -exec cp {} ./afterGamesReport \;

