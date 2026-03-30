# copy .pgn files created in the last 2 hours to afterGamesReport
# exclude INSTALL/, openingRepertoire/, and venv/ directories
find . -name "*.pgn" -type f -mmin -120 \
    -not -path "./afterGamesReport/*" \
    -not -path "./INSTALL/*" \
    -not -path "./openingRepertoire/*" \
    -not -path "*/venv/*" \
    -exec cp {} ./afterGamesReport \;
