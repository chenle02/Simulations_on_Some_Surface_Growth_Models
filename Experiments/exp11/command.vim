" Autocommand for opening dzi_config.yaml
" autocmd BufRead,BufEnter, dzi_config.yaml call SetupDziCommands()
" autocmd BufRead,BufEnter, dzi_config.yaml nnoremap <buffer> <leader><leader> :call Dzi()<CR>

" Define the custom function and mapping
" function! SetupDziCommands()
"     " Check if the current buffer is for dzi_config.yaml
"     if expand('%:t') == 'dzi_config.yaml'
"         " Define a buffer-local command for the key mapping
"         nnoremap <buffer> <leader><enter> :call Dzi()<CR>
"     endif
" endfunction

function! Dzi()
    " Save the file
    write
    " Run the file with Python3
    !python3 gen_openseadragon.py
    " Open the result in qutebrowser, assuming qutebrowser is installed and in your PATH
    execute "!qutebrowser ./dzi_images/index.html &"
endfunction
