document.addEventListener('DOMContentLoaded', function () {
  if (window.TableKit) {
    TableKit.init({
      table: '#tabla-historial',
      pagerContainer: '#paginationHist',
      infoContainer: '#tableInfoHist',
      pageLenKey: 'obligaciones_historial_page_len',
      defaultPageLen: 10,
    });
  }
});
